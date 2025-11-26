use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Trace data structure for function call tracking.
///
/// Represents a single trace entry containing information about
/// a function call, including its arguments, execution timestamp, and optional result.
///
/// # Examples
///
/// ```
/// use trace_common::TraceData;
/// use serde_json::json;
///
/// let args = json!({"param": "value"});
/// let trace = TraceData::new("my_function", args);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TraceData {
    /// UTC timestamp when the trace was created
    pub timestamp: DateTime<Utc>,
    /// Name of the function being traced
    pub function_name: String,
    /// Function arguments as JSON value
    pub args: serde_json::Value,
    /// Optional function result as JSON value
    pub result: Option<serde_json::Value>,
}

impl TraceData {
    /// Creates a new trace entry with current timestamp.
    ///
    /// # Arguments
    ///
    /// * `function_name` - Name of the function being traced
    /// * `args` - Function arguments as a JSON value
    ///
    /// # Examples
    ///
    /// ```
    /// use trace_common::TraceData;
    /// use serde_json::json;
    ///
    /// let trace = TraceData::new("example_fn", json!({"x": 42}));
    /// assert_eq!(trace.function_name, "example_fn");
    /// ```
    pub fn new(function_name: impl Into<String>, args: serde_json::Value) -> Self {
        Self {
            timestamp: Utc::now(),
            function_name: function_name.into(),
            args,
            result: None,
        }
    }

    /// Sets the result value for this trace entry (builder pattern).
    ///
    /// # Arguments
    ///
    /// * `result` - The result value to set
    ///
    /// # Examples
    ///
    /// ```
    /// use trace_common::TraceData;
    /// use serde_json::json;
    ///
    /// let trace = TraceData::new("example_fn", json!({"x": 42}))
    ///     .with_result(json!({"output": "success"}));
    /// ```
    pub fn with_result(mut self, result: serde_json::Value) -> Self {
        self.result = Some(result);
        self
    }

    /// Updates the result value for this trace entry.
    ///
    /// # Arguments
    ///
    /// * `result` - The result value to set
    pub fn set_result(&mut self, result: serde_json::Value) {
        self.result = Some(result);
    }
}

/// Serializes any value implementing [`Serialize`] trait.
///
/// Returns error information as JSON string if serialization fails.
/// This function provides safe serialization with graceful error handling.
///
/// # Arguments
///
/// * `value` - The value to serialize
///
/// # Examples
///
/// ```
/// use trace_common::serialize_value;
/// use serde_json::json;
///
/// let result = serialize_value(&42);
/// assert_eq!(result, json!(42));
/// ```
pub fn serialize_value<T: Serialize>(value: &T) -> serde_json::Value {
    serde_json::to_value(value).unwrap_or_else(|e| {
        serde_json::Value::String(format!(
            "<serialization_failed: {} - {}>",
            std::any::type_name::<T>(),
            e
        ))
    })
}

/// Generates a placeholder for any type with type information.
///
/// This function creates a JSON string placeholder that includes the type name
/// for debugging purposes. For types implementing [`std::fmt::Debug`], it also
/// includes the debug representation.
///
/// # Arguments
///
/// * `_value` - The value to create placeholder for (for type inference)
///
/// # Examples
///
/// ```
/// use trace_common::placeholder_for;
/// use std::rc::Rc;
///
/// let rc_value = Rc::new(42);
/// let placeholder = placeholder_for(&rc_value);
/// // Returns: "<unserializable: alloc::rc::Rc<i32>>"
/// ```
pub fn placeholder_for<T>(_value: &T) -> serde_json::Value {
    serde_json::Value::String(format!("<unserializable: {}>", std::any::type_name::<T>()))
}

/// Generates a debug placeholder for types implementing [`std::fmt::Debug`].
///
/// This function creates a JSON string that includes both the type name and
/// debug representation of the value.
///
/// # Arguments
///
/// * `value` - The value to create debug placeholder for
///
/// # Examples
///
/// ```
/// use trace_common::debug_placeholder_for;
/// use std::rc::Rc;
///
/// let rc_value = Rc::new(vec![1, 2, 3]);
/// let placeholder = debug_placeholder_for(&rc_value);
/// // Returns: "<debug: alloc::rc::Rc<alloc::vec::Vec<i32>> = [1, 2, 3]>"
/// ```
pub fn debug_placeholder_for<T: std::fmt::Debug>(value: &T) -> serde_json::Value {
    serde_json::Value::String(format!(
        "<debug: {} = {:?}>",
        std::any::type_name::<T>(),
        value
    ))
}

/// Macro for serializing values that implement [`Serialize`].
///
/// This macro attempts to serialize the given value using [`serialize_value`].
///
/// # Examples
///
/// ```
/// use trace_common::serialize_value;
/// use serde_json::json;
///
/// let value = 42;
/// let result = serialize_value!(&value);
/// assert_eq!(result, json!(42));
/// ```
#[macro_export]
macro_rules! serialize_value {
    ($value:expr) => {{
        $crate::serialize_value(&$value)
    }};
}

/// Macro for creating placeholders for non-serializable types.
///
/// This macro creates a placeholder for values that cannot be serialized,
/// providing type information for debugging.
///
/// # Examples
///
/// ```
/// use trace_common::placeholder_for;
/// use std::rc::Rc;
///
/// let rc_value = Rc::new(42);
/// let result = placeholder_for!(&rc_value);
/// // Returns a placeholder string with type information
/// ```
#[macro_export]
macro_rules! placeholder_for {
    ($value:expr) => {{
        $crate::placeholder_for($value)
    }};
}

/// Creates JSON object with parameter names and values.
///
/// Used for building JSON objects from parameter name-value pairs.
/// Each parameter specifies a serialization strategy (either `serialize_value`
/// or `placeholder_for`).
///
/// # Examples
///
/// ```
/// use trace_common::{args_json, serialize_value};
/// use serde_json::json;
///
/// let param1 = 42;
/// let param2 = "test";
///
/// let args = args_json!(
///     "param1" => serialize_value!(&param1),
///     "param2" => serialize_value!(&param2)
/// );
///
/// assert_eq!(args, json!({"param1": 42, "param2": "test"}));
/// ```
#[macro_export]
macro_rules! args_json {
    () => {{
        ::serde_json::Value::Object(::serde_json::Map::new())
    }};
    ($($name:expr => $value:expr),+ $(,)?) => {{
        let mut map = ::serde_json::Map::new();
        $(
            map.insert($name.to_string(), $value);
        )*
        ::serde_json::Value::Object(map)
    }};
}

/// Re-export commonly used types for convenience
pub use serde_json::Value as JsonValue;

/// Attempts to serialize a value if it implements [`Serialize`].
///
/// Falls back to type name placeholder if serialization fails.
#[macro_export]
macro_rules! serialize_if_serializable {
    ($value:expr) => {{
        $crate::serialize_value($value)
    }};
}

/// Safely serializes any value with graceful error handling.
///
/// Creates a debug placeholder for types that don't implement [`Serialize`].
#[macro_export]
macro_rules! safe_serialize_any {
    ($value:expr) => {{
        $crate::placeholder_for($value)
    }};
}

/// Creates a JSON object from function argument tuples.
///
/// Each tuple contains: (name, value_ref, serialization_method).
/// The serialization method should be either `serialize_if_serializable` or `safe_serialize_any`.
///
/// # Examples
///
/// ```
/// use trace_common::{create_args_json, serialize_if_serializable, safe_serialize_any};
/// 
/// let x = 42;
/// let y = "test";
/// let args = create_args_json!(
///     ("x", &x, serialize_if_serializable),
///     ("y", &y, serialize_if_serializable)
/// );
/// ```
#[macro_export]
macro_rules! create_args_json {
    () => {{
        ::serde_json::Value::Object(::serde_json::Map::new())
    }};
    ($(($name:expr, $value:expr, $method:ident)),+ $(,)?) => {{
        let mut map = ::serde_json::Map::new();
        $(
            map.insert($name.to_string(), $crate::$method!($value));
        )+
        ::serde_json::Value::Object(map)
    }};
}
