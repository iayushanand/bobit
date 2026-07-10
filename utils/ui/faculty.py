import discord
from discord import ui


def build_department_embed(dept: dict) -> discord.Embed:
    name = dept['name']
    since = dept['started']
    hod_name = dept['hod_name']
    email = dept['email']
    image = dept['image']
    desc = (
        dept["description"][:300] + "..."
        if len(dept["description"]) > 300
        else dept["description"]
    )
    stats = dept['stats']

    embed = discord.Embed(title=name, description=desc, color=0x2b2d31)
    embed.add_field(name="Since", value=since, inline=True)
    embed.add_field(name="HOD", value=hod_name, inline=True)
    embed.add_field(name="Email", value=f"[{email}](mailto:{email})", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    for stat in stats:
        embed.add_field(
            name=stat.replace("_", " ").title(),
            value=stats[stat],
            inline=True,
        )
    embed.set_thumbnail(url=image)
    embed.set_footer(text=f"Department of {name}")
    return embed


def build_hod_embed(dept: dict) -> discord.Embed:
    hod = dept['hod']
    embed = discord.Embed(
        title=hod['name'],
        description=f"**Head of Department** — {dept['name']}",
        color=0x57f287,
    )
    embed.set_image(url=hod.get('image', ''))
    embed.add_field(name="Designation", value=hod.get('designation', 'N/A'), inline=True)
    embed.add_field(name="Qualification", value=hod.get('qualification', 'N/A'), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    hod_email = hod.get('email', 'N/A')
    embed.add_field(name="Email", value=f"[{hod_email}](mailto:{hod_email})" if hod_email != 'N/A' else 'N/A', inline=True)
    embed.add_field(name="Contact", value=hod.get('contact', 'N/A'), inline=True)
    if hod.get('read_more'):
        embed.add_field(name="\u200b", value=f"[View Full Profile]({hod['read_more']})", inline=False)
    embed.set_footer(text=f"HOD • {dept['name']}")
    return embed


def build_teaching_embed(faculty: dict, dept: dict) -> discord.Embed:
    details = faculty.get('details', {})
    embed = discord.Embed(
        title=faculty['name'],
        description=f"**{faculty.get('designation', '')}** — {dept['name']}",
        color=0x5865f2,
    )
    embed.set_image(url=details.get('image', faculty.get('thumbnail', '')))
    embed.add_field(name="Qualification", value=details.get('qualification', 'N/A'), inline=True)
    embed.add_field(name="Specialization", value=details.get('specialization', 'N/A'), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    fac_email = details.get('email', 'N/A')
    embed.add_field(name="Email", value=f"[{fac_email}](mailto:{fac_email})" if fac_email != 'N/A' else 'N/A', inline=True)
    embed.add_field(name="Phone", value=details.get('phone', 'N/A'), inline=True)
    if details.get('teaching_interest'):
        interest = details['teaching_interest']
        if len(interest) > 200:
            interest = interest[:200] + "..."
        embed.add_field(name="Teaching Interest", value=interest, inline=False)
    if faculty.get('profile_url'):
        embed.add_field(name="\u200b", value=f"[View Full Profile]({faculty['profile_url']})", inline=False)
    embed.set_footer(text=f"Teaching Faculty • {dept['name']}")
    return embed


def build_non_teaching_embed(staff: dict, dept: dict) -> discord.Embed:
    embed = discord.Embed(
        title=staff['name'],
        description=f"**{staff.get('designation', '')}** — {dept['name']}",
        color=0x99aab5,
    )
    embed.set_image(url=staff.get('image', ''))
    embed.add_field(name="Designation", value=staff.get('designation', 'N/A'), inline=True)
    embed.add_field(name="Phone", value=staff.get('phone', 'N/A'), inline=True)
    embed.set_footer(text=f"Non-Teaching Staff • {dept['name']}")
    return embed


class FacultyView(ui.View):
    def __init__(self, dept: dict, author_id: int):
        super().__init__(timeout=120)
        self.dept = dept
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    @ui.button(label="HOD", style=discord.ButtonStyle.green)
    async def hod_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = build_hod_embed(self.dept)
        view = HODView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Teaching", style=discord.ButtonStyle.gray)
    async def teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        teaching = self.dept.get('teaching', [])
        if not teaching:
            await interaction.response.send_message("No teaching faculty found.", ephemeral=True)
            return
        view = TeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Teaching Faculty — {self.dept['name']}",
            description=f"Select a faculty member from the dropdown below.\n**{len(teaching)}** teaching faculty available.",
            color=0x5865f2,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Non Teaching", style=discord.ButtonStyle.gray)
    async def non_teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        non_teaching = self.dept.get('non_teaching', [])
        if not non_teaching:
            await interaction.response.send_message("No non-teaching staff found.", ephemeral=True)
            return
        view = NonTeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Non-Teaching Staff — {self.dept['name']}",
            description=f"Select a staff member from the dropdown below.\n**{len(non_teaching)}** non-teaching staff available.",
            color=0x99aab5,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)


class HODView(ui.View):
    def __init__(self, dept: dict, author_id: int):
        super().__init__(timeout=120)
        self.dept = dept
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    @ui.button(label="Department", style=discord.ButtonStyle.blurple)
    async def dept_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = build_department_embed(self.dept)
        view = FacultyView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Teaching", style=discord.ButtonStyle.gray)
    async def teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        teaching = self.dept.get('teaching', [])
        if not teaching:
            await interaction.response.send_message("No teaching faculty found.", ephemeral=True)
            return
        view = TeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Teaching Faculty — {self.dept['name']}",
            description=f"Select a faculty member from the dropdown below.\n**{len(teaching)}** teaching faculty available.",
            color=0x5865f2,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Non Teaching", style=discord.ButtonStyle.gray)
    async def non_teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        non_teaching = self.dept.get('non_teaching', [])
        if not non_teaching:
            await interaction.response.send_message("No non-teaching staff found.", ephemeral=True)
            return
        view = NonTeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Non-Teaching Staff — {self.dept['name']}",
            description=f"Select a staff member from the dropdown below.\n**{len(non_teaching)}** non-teaching staff available.",
            color=0x99aab5,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)


class FacultyDetailView(ui.View):
    def __init__(self, dept: dict, author_id: int):
        super().__init__(timeout=120)
        self.dept = dept
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    @ui.button(label="Department", style=discord.ButtonStyle.blurple)
    async def dept_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = build_department_embed(self.dept)
        view = FacultyView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="HOD", style=discord.ButtonStyle.green)
    async def hod_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = build_hod_embed(self.dept)
        view = HODView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Teaching", style=discord.ButtonStyle.gray)
    async def teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        teaching = self.dept.get('teaching', [])
        if not teaching:
            await interaction.response.send_message("No teaching faculty found.", ephemeral=True)
            return
        view = TeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Teaching Faculty — {self.dept['name']}",
            description=f"Select a faculty member from the dropdown below.\n**{len(teaching)}** teaching faculty available.",
            color=0x5865f2,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Non Teaching", style=discord.ButtonStyle.gray)
    async def non_teaching_button(self, interaction: discord.Interaction, button: ui.Button):
        non_teaching = self.dept.get('non_teaching', [])
        if not non_teaching:
            await interaction.response.send_message("No non-teaching staff found.", ephemeral=True)
            return
        view = NonTeachingSelectView(self.dept, self.author_id)
        embed = discord.Embed(
            title=f"Non-Teaching Staff — {self.dept['name']}",
            description=f"Select a staff member from the dropdown below.\n**{len(non_teaching)}** non-teaching staff available.",
            color=0x99aab5,
        )
        embed.set_thumbnail(url=self.dept.get('image', ''))
        await interaction.response.edit_message(embed=embed, view=view)


class TeachingSelect(ui.Select):
    def __init__(self, dept: dict, author_id: int, chunk: list[tuple[int, dict]], start: int, end: int, row: int):
        self.dept = dept
        self.author_id = author_id
        options = [
            discord.SelectOption(
                label=f['name'][:100],
                description=(f.get('designation', ''))[:100],
                value=str(i),
            )
            for i, f in chunk
        ]
        super().__init__(
            placeholder=f"Teaching faculty {start}–{end}",
            options=options,
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        faculty = self.dept['teaching'][idx]
        embed = build_teaching_embed(faculty, self.dept)
        view = FacultyDetailView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)


class NavDeptButton(ui.Button):
    def __init__(self, dept: dict, author_id: int, row: int):
        super().__init__(label="Department", style=discord.ButtonStyle.blurple, row=row)
        self.dept = dept
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        embed = build_department_embed(self.dept)
        view = FacultyView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)


class NavHODButton(ui.Button):
    def __init__(self, dept: dict, author_id: int, row: int):
        super().__init__(label="HOD", style=discord.ButtonStyle.green, row=row)
        self.dept = dept
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        embed = build_hod_embed(self.dept)
        view = HODView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)


class TeachingSelectView(ui.View):
    def __init__(self, dept: dict, author_id: int):
        super().__init__(timeout=120)
        self.dept = dept
        self.author_id = author_id
        teaching = dept.get('teaching', [])
        for chunk_idx in range(0, min(len(teaching), 75), 25):
            chunk = list(enumerate(teaching[chunk_idx:chunk_idx + 25], start=chunk_idx))
            start = chunk_idx + 1
            end = chunk_idx + len(chunk)
            row = chunk_idx // 25
            self.add_item(TeachingSelect(dept, author_id, chunk, start, end, row=row))
        btn_row = min(len(teaching) // 25 + (1 if len(teaching) % 25 else 0), 3)
        self.add_item(NavDeptButton(dept, author_id, row=btn_row))
        self.add_item(NavHODButton(dept, author_id, row=btn_row))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True


class NonTeachingSelect(ui.Select):
    def __init__(self, dept: dict, author_id: int, chunk: list[tuple[int, dict]], start: int, end: int, row: int):
        self.dept = dept
        self.author_id = author_id
        options = [
            discord.SelectOption(
                label=s['name'][:100],
                description=(s.get('designation', ''))[:100],
                value=str(i),
            )
            for i, s in chunk
        ]
        super().__init__(
            placeholder=f"Non-teaching staff {start}–{end}",
            options=options,
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        staff = self.dept['non_teaching'][idx]
        embed = build_non_teaching_embed(staff, self.dept)
        view = FacultyDetailView(self.dept, self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)


class NonTeachingSelectView(ui.View):
    def __init__(self, dept: dict, author_id: int):
        super().__init__(timeout=120)
        self.dept = dept
        self.author_id = author_id
        non_teaching = dept.get('non_teaching', [])
        for chunk_idx in range(0, min(len(non_teaching), 75), 25):
            chunk = list(enumerate(non_teaching[chunk_idx:chunk_idx + 25], start=chunk_idx))
            start = chunk_idx + 1
            end = chunk_idx + len(chunk)
            row = chunk_idx // 25
            self.add_item(NonTeachingSelect(dept, author_id, chunk, start, end, row=row))
        btn_row = min(len(non_teaching) // 25 + (1 if len(non_teaching) % 25 else 0), 3)
        self.add_item(NavDeptButton(dept, author_id, row=btn_row))
        self.add_item(NavHODButton(dept, author_id, row=btn_row))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True
