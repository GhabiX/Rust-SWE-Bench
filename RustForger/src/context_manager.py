from dataclasses import dataclass
from typing import List, Optional
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import copy


@dataclass
class ContextConfig:
    enable_trimming: bool = False  
    max_turns: int = 50           
    keep_recent_turns: int = 20   
    trim_start_turn: int = 2      
    trim_head_lines: int = 15     
    trim_tail_lines: int = 15     
    trim_first_ai_message: bool = True 


def trim_message_content(content: str, head_lines: int = 15, tail_lines: int = 15) -> str:

    if not content:
        return content
        
    lines = content.split('\n')
    total_lines = len(lines)
    
    if total_lines <= head_lines + tail_lines:
        return content

    head_content = '\n'.join(lines[:head_lines])
    tail_content = '\n'.join(lines[-tail_lines:])
    
    omitted_lines = total_lines - head_lines - tail_lines
    
    trimmed_content = f"{head_content}\n\n... [OMITTED {omitted_lines} lines] ...\n\n{tail_content}"
    
    return trimmed_content


def create_trimmed_history(
    original_history: ChatMessageHistory, 
    config: ContextConfig,
    current_turn: int
) -> ChatMessageHistory:

    trimmed_history = ChatMessageHistory()
    
    messages = original_history.messages
    
    if not config.enable_trimming or len(messages) <= 2:
        for message in messages:
            trimmed_history.add_message(message)
        return trimmed_history
    
    trim_start_idx = (config.trim_start_turn - 1) * 2  
    
    recent_start_idx = max(0, len(messages) - config.keep_recent_turns * 2)
    
    for i, message in enumerate(messages):
        if i == 0:
            trimmed_history.add_message(message)
        elif i == 1:
            if config.trim_first_ai_message:
                trimmed_content = trim_message_content(
                    message.content, 
                    config.trim_head_lines, 
                    config.trim_tail_lines
                )
                trimmed_message = copy.deepcopy(message)
                trimmed_message.content = trimmed_content
                trimmed_history.add_message(trimmed_message)
            else:
                trimmed_history.add_message(message)
        elif i >= trim_start_idx and i < recent_start_idx:
            trimmed_content = trim_message_content(
                message.content, 
                config.trim_head_lines, 
                config.trim_tail_lines
            )

            trimmed_message = copy.deepcopy(message)
            trimmed_message.content = trimmed_content
                
            trimmed_history.add_message(trimmed_message)
        else:
            trimmed_history.add_message(message)
    
    return trimmed_history


def get_current_turn_from_history(history: ChatMessageHistory) -> int:

    return (len(history.messages) // 2) + 1 