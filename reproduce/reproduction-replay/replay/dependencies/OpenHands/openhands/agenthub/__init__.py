from dotenv import load_dotenv
from openhands.agenthub.micro.agent import MicroAgent
from openhands.agenthub.micro.registry import all_microagents
from openhands.controller.agent import Agent

load_dotenv()


from openhands.agenthub import browsing_agent  # noqa: E402
from openhands.agenthub import codeact_agent
from openhands.agenthub import delegator_agent
from openhands.agenthub import dummy_agent
from openhands.agenthub import visualbrowsing_agent

__all__ = [
    'codeact_agent',
    'delegator_agent',
    'dummy_agent',
    'browsing_agent',
    'visualbrowsing_agent',
]

for agent in all_microagents.values():
    name = agent['name']
    prompt = agent['prompt']

    anon_class = type(
        name,
        (MicroAgent,),
        {
            'prompt': prompt,
            'agent_definition': agent,
        },
    )

    Agent.register(name, anon_class)
