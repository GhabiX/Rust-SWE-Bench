"""
Utility decorators for function enhancement and debugging.

This module provides a collection of decorators that enhance function behavior:

- func_retry: Automatically retry functions that raise exceptions with configurable
  delay and maximum attempts
- func_debug: Debug decorator that prints detailed argument and error information
  when functions fail, useful for troubleshooting
- lazy: Lazy evaluation decorator for properties that caches computed values

These decorators are designed to be composable and can be used together to
create robust, debuggable, and efficient functions.
"""

import functools
import time
from typing import Any
from typing import Callable


def func_retry(
    max_attempts: int = 5,
    delay: float = 1.0,
) -> Callable:
    """
    Create a retry decorator for functions that may fail transiently.

    This decorator automatically retries function execution when exceptions occur,
    with configurable maximum attempts and delay between retries. Useful for
    network operations, file I/O, or other operations that might fail temporarily.

    Args:
        max_attempts: Maximum number of execution attempts (including the initial attempt).
                     Must be >= 1. Default is 5.
        delay: Number of seconds to wait between retry attempts. Can be fractional.
               Default is 1.0 second.

    Returns:
        Callable: A decorator function that can be applied to other functions

    Examples:
        >>> @func_retry(max_attempts=3, delay=0.5)
        ... def unstable_network_call():
        ...     # Function that might fail
        ...     pass
        
        >>> # With default parameters
        >>> @func_retry()
        ... def flaky_operation():
        ...     pass

    Note:
        The last exception is re-raised if all attempts fail. The delay is constant
        between retries (not exponential backoff).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            while attempts < max_attempts:
                try:
                    # Attempt to execute the decorated function
                    return func(*args, **kwargs)
                except Exception:
                    attempts += 1
                    # If this was the last attempt, re-raise the exception
                    if attempts == max_attempts:
                        raise
                    # Wait before the next retry attempt
                    time.sleep(delay)

        return wrapper

    return decorator


def func_debug(func: Callable) -> Callable:
    """
    Create a debug decorator that provides detailed error diagnostics.

    This decorator wraps functions to print comprehensive debugging information
    when exceptions occur, including all positional and keyword arguments.
    Useful for troubleshooting function calls in complex systems.

    Args:
        func: The function to wrap with debugging capabilities

    Returns:
        Callable: The wrapped function that prints debug info on exceptions

    Examples:
        >>> @func_debug
        ... def problematic_function(x, y, option=None):
        ...     if x < 0:
        ...         raise ValueError("x must be positive")
        ...     return x + y

        >>> # When called with invalid args, prints detailed debug info
        >>> problematic_function(-1, 5, option="test")
        ## args 0 ##
         -1
        ## args 1 ##
         5
        ## kwargs option ##
         test
        ## error ##
         x must be positive

    Note:
        The original exception is re-raised after printing debug information.
        Debug output goes to stdout, so consider logging implications in
        production environments.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            # Attempt to execute the decorated function normally
            return func(*args, **kwargs)
        except Exception as e:
            # Print detailed debugging information
            
            # Display all positional arguments with their indices
            for idx, arg in enumerate(args):
                print(f"## args {idx} ##\n {arg}")
            
            # Display all keyword arguments with their names
            for key, val in kwargs.items():
                print(f"## kwargs {key} ##\n {val}")
            
            # Display the exception information
            print(f"## error ##\n {e}")
            
            # Re-raise the original exception to preserve the call stack
            raise e

    return wrapper


def lazy(
    func: Callable,
) -> Callable:
    """
    Create a lazy evaluation decorator for class properties.

    This decorator transforms a method into a lazy property that computes its value
    only once and caches the result for subsequent accesses. Useful for expensive
    computations that should only be performed when needed.

    The cached value is stored as a private attribute on the instance using a
    hash-based naming scheme to avoid naming conflicts.

    Args:
        func: The method to make lazy. Should be a method that takes only 'self'
              as an argument and returns a value to be cached.

    Returns:
        Callable: A property-like function that caches its result after first call

    Examples:
        >>> class DataProcessor:
        ...     @lazy
        ...     def expensive_computation(self):
        ...         print("Computing...")  # This will only print once
        ...         return sum(range(1000000))
        ...
        >>> processor = DataProcessor()
        >>> result1 = processor.expensive_computation  # Prints "Computing..."
        >>> result2 = processor.expensive_computation  # Uses cached value

    Note:
        - This decorator is designed for instance methods, not static functions
        - The cached value persists for the lifetime of the instance
        - No cache invalidation mechanism is provided
        - Thread safety is not guaranteed in concurrent environments
    """
    # Generate a unique attribute name for storing the cached value
    # Using hash to avoid naming conflicts with other lazy properties
    _attr_name_ = "__lazy_" + str(hash(func.__name__)) + "_lazy__"

    def _lazy(self):
        """
        Lazy property implementation that checks cache and computes if needed.
        
        Args:
            self: The instance on which the property is being accessed
            
        Returns:
            The cached or newly computed value from the original function
        """
        # Check if the cached value already exists
        if not hasattr(self, _attr_name_):
            # Compute and cache the value on first access
            setattr(self, _attr_name_, func(self))
        # Return the cached value
        return getattr(self, _attr_name_)

    return _lazy
