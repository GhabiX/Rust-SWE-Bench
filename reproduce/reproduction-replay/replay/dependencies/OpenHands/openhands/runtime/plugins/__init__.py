# Requirements
from openhands.runtime.plugins.agent_skills import AgentSkillsPlugin
from openhands.runtime.plugins.agent_skills import AgentSkillsRequirement
from openhands.runtime.plugins.jupyter import JupyterPlugin
from openhands.runtime.plugins.jupyter import JupyterRequirement
from openhands.runtime.plugins.requirement import Plugin
from openhands.runtime.plugins.requirement import PluginRequirement
from openhands.runtime.plugins.vscode import VSCodePlugin
from openhands.runtime.plugins.vscode import VSCodeRequirement

__all__ = [
    'Plugin',
    'PluginRequirement',
    'AgentSkillsRequirement',
    'AgentSkillsPlugin',
    'JupyterRequirement',
    'JupyterPlugin',
    'VSCodeRequirement',
    'VSCodePlugin',
]

ALL_PLUGINS = {
    'jupyter': JupyterPlugin,
    'agent_skills': AgentSkillsPlugin,
    'vscode': VSCodePlugin,
}
