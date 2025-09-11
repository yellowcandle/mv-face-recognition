"""
Theme configuration for the NiceGUI application.
"""

from nicegui import ui


class AppTheme:
    def __init__(self):
        self.primary_color = "#0d7377"
        self.secondary_color = "#14a085"
        self.accent_color = "#32e0c4"
        self.dark_color = "#212121"
        self.light_color = "#eeeeee"

    def set_theme(self):
        """Apply the custom theme to the UI."""
        ui.colors(
            primary=self.primary_color,
            secondary=self.secondary_color,
            accent=self.accent_color,
            dark=self.dark_color,
            positive="#21BA45",
            negative="#C10015",
            info="#31CCEC",
            warning="#F2C037",
        )

        # Custom CSS for a more polished look
        ui.add_head_html(f"""
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap');
                
                body {{
                    font-family: 'Inter', sans-serif;
                }}
                
                .q-header {{
                    background-color: {self.dark_color} !important;
                }}
                
                .q-footer {{
                    background-color: {self.dark_color} !important;
                }}

                .q-tab__label {{
                    font-weight: 700;
                }}
            </style>
        """)


theme = AppTheme()
