"""Agent core module."""

from nanobot.agent.context import ContextBuilder
from nanobot.agent.hook import AgentHook, AgentHookContext, CompositeHook
from nanobot.agent.loop import AgentLoop
from nanobot.agent.memory import MemoryStore
from nanobot.agent.philosopher import PhilosopherAgent
from nanobot.agent.skills import SkillsLoader
from nanobot.agent.summarizer import BackgroundSummarizer
from nanobot.agent.subagent import SubagentManager

__all__ = [
    "AgentHook",
    "AgentHookContext",
    "AgentLoop",
    "BackgroundSummarizer",
    "CompositeHook",
    "ContextBuilder",
    "MemoryStore",
    "PhilosopherAgent",
    "SkillsLoader",
    "SubagentManager",
]
