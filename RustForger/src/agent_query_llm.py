import os
import json
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from typing import Optional

from agent_prompt import rta_system_prompt
from context_manager import ContextConfig, create_trimmed_history, get_current_turn_from_history
# from rta_prompt_acr import rta_system_prompt
# from rta_prompt_agentless import rta_system_prompt

# Cost calculation constants for Claude pricing
# Input: $3/1M tokens, Output: $15/1M tokens
# INPUT_COST_PER_TOKEN = 1.1 / 1_000_000  # $0.000003 per token
# OUTPUT_COST_PER_TOKEN = 4.4 / 1_000_000  # $0.000015 per token
# INPUT_COST_PER_TOKEN = 0.7 / 1_000_000  # $0.000003 per token
# OUTPUT_COST_PER_TOKEN = 2.8 / 1_000_000  # $0.000015 per token
INPUT_COST_PER_TOKEN = 3.0 / 1_000_000  # $0.000003 per token
OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000  # $0.000015 per token


base_url="url"

api_key = "sk-key" 


message_history_store = {}

def get_session_history(session_id: str):
    if session_id not in message_history_store:
        message_history_store[session_id] = ChatMessageHistory()
    return message_history_store[session_id]

def init_runnable(workspace_path: str, model_name: str, context_config: Optional[ContextConfig] = None):
    llm = ChatOpenAI(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        request_timeout=180,
        max_retries=3,
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", rta_system_prompt.format(issue_repo_path=workspace_path)),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    runnable = RunnableWithMessageHistory(
        prompt_template | llm,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )
    
    return runnable

def query_llm(runnable, prompt: str, session_id: str = "default_session", context_config: Optional[ContextConfig] = None, log_trimmed_context: bool = False, log_file_path: str = None):
    config = {"configurable": {"session_id": session_id}}
    

    if context_config and context_config.enable_trimming:

        original_history = get_session_history(session_id)
        current_turn = get_current_turn_from_history(original_history)
        

        trimmed_history = create_trimmed_history(original_history, context_config, current_turn)
        

        if log_trimmed_context and log_file_path:
            try:
                import os
                from datetime import datetime
                
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
                
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Session ID: {session_id}\n")
                    f.write(f"Current Turn: {current_turn + 1}\n")
                    f.write(f"Original history message count: {len(original_history.messages)}\n")
                    f.write(f"Trimmed history message count: {len(trimmed_history.messages)}\n")
                    f.write(f"{'='*80}\n\n")
                    
                    # Output trimmed history
                    f.write("=== Trimmed History ===\n")
                    for i, message in enumerate(trimmed_history.messages):
                        turn_num = (i // 2) + 1
                        msg_type = "User" if i % 2 == 0 else "AI"
                        f.write(f"\n--- Turn {turn_num} {msg_type} Message ---\n")
                        f.write(message.content)
                        f.write(f"\n--- Message End ({len(message.content.split(chr(10)))} lines) ---\n")
                    
                    # Output current new user input
                    f.write(f"\n=== Current User Input ===\n")
                    f.write(prompt)
                    f.write(f"\n=== Input End ===\n\n")
                    
            except Exception as e:
                print(f"Failed to write context log: {e}")
        
        # Temporarily replace history store with trimmed version
        original_store_entry = message_history_store.get(session_id)
        message_history_store[session_id] = trimmed_history
        
        try:

            response = runnable.invoke({"input": prompt}, config=config)
            result = response.content
        finally:
            # Restore original history store
            if original_store_entry is not None:
                message_history_store[session_id] = original_store_entry
            else:
                # If there was no original history, remove the temporary entry
                message_history_store.pop(session_id, None)
        
        # Only add new conversation to original history (RunnableWithMessageHistory won't automatically add to original history)
        original_history.add_user_message(prompt)
        # Create AI message with complete metadata
        ai_message = AIMessage(
            content=result,
            additional_kwargs=getattr(response, 'additional_kwargs', {}),
            response_metadata=getattr(response, 'response_metadata', {}),
            name=getattr(response, 'name', None),
            id=getattr(response, 'id', None)
        )
        original_history.add_message(ai_message)
        
        # Calculate cost based on token usage
        token_usage = getattr(response, 'response_metadata', {}).get('token_usage', {})
        prompt_tokens = token_usage.get('prompt_tokens', 0)
        completion_tokens = token_usage.get('completion_tokens', 0)
        
        # Calculate total cost
        cost = (prompt_tokens * INPUT_COST_PER_TOKEN + 
                completion_tokens * OUTPUT_COST_PER_TOKEN)
        
        # Return structured response with cost information
        return {
            "content": result,
            "cost": cost,
            "tokens": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": token_usage.get('total_tokens', prompt_tokens + completion_tokens)
            }
        }
    else:
        # When trimming is not enabled, use original logic
        response = runnable.invoke({"input": prompt}, config=config)
        
        # Calculate cost based on token usage
        token_usage = getattr(response, 'response_metadata', {}).get('token_usage', {})
        prompt_tokens = token_usage.get('prompt_tokens', 0)
        completion_tokens = token_usage.get('completion_tokens', 0)
        
        # Calculate total cost
        cost = (prompt_tokens * INPUT_COST_PER_TOKEN + 
                completion_tokens * OUTPUT_COST_PER_TOKEN)
        
        # Return structured response with cost information
        return {
            "content": response.content,
            "cost": cost,
            "tokens": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": token_usage.get('total_tokens', prompt_tokens + completion_tokens)
            }
        }

def load_session_history_from_json(json_file_path: str, session_id: str = "loaded_session") -> ChatMessageHistory:
    """
    Load conversation history from a JSON file
    
    Args:
        json_file_path: Path to the JSON file
        session_id: Session ID for the loaded history (default: "loaded_session")
        
    Returns:
        ChatMessageHistory object with the loaded conversation
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        history = ChatMessageHistory()
        
        # Map message types to appropriate message classes
        type_to_class = {
            'human': HumanMessage,
            'ai': AIMessage
        }
        
        # Add messages to history
        for msg in history_data.get('messages', []):
            msg_type = msg.get('type', '')
            if msg_type in type_to_class:
                # Preserve all metadata information
                message = type_to_class[msg_type](
                    content=msg.get('content', ''),
                    additional_kwargs=msg.get('additional_kwargs', {}),
                    response_metadata=msg.get('response_metadata', {}),
                    name=msg.get('name', None),
                    id=msg.get('id', None)
                )
                history.add_message(message)
        
        # Store in global message history
        message_history_store[session_id] = history
        return history
    except Exception as e:
        print(f"Error loading history: {str(e)}")
        return ChatMessageHistory()


