"""
Application registry for the Athena OS Tool.
"""

APPLICATIONS = {
    "vs_code": {
        "display_name": "Visual Studio Code",
        "command": ["code"],
        "aliases": [
            "vs code",
            "vscode",
            "visual studio code",
            "code",
        ],
    },

    "notepad": {
        "display_name": "Notepad",
        "command": ["notepad"],
        "aliases": [
            "notepad",
        ],
    },

    "calculator": {
        "display_name": "Calculator",
        "command": ["calc"],
        "aliases": [
            "calculator",
            "calc",
        ],
    },

    "paint": {
        "display_name": "Paint",
        "command": ["mspaint"],
        "aliases": [
            "paint",
        ],
    },

    "explorer": {
        "display_name": "File Explorer",
        "command": ["explorer"],
        "aliases": [
            "explorer",
            "file explorer",
            "files",
        ],
    },

    "cmd": {
        "display_name": "Command Prompt",
        "command": ["cmd"],
        "aliases": [
            "cmd",
            "command prompt",
            "terminal",
        ],
    },

    "powershell": {
        "display_name": "PowerShell",
        "command": ["powershell"],
        "aliases": [
            "powershell",
        ],
    },
}