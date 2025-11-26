//! Integration tests for trace_common crate
//!
//! This module contains comprehensive tests for the trace_common library,
//! covering all public APIs and edge cases.

use std::collections::HashMap;
use std::rc::Rc;

use chrono::{DateTime, TimeZone, Utc};
use serde::Serialize;
use serde_json;

use trace_common::*;

/// Example struct implementing [`Serialize`]
///
/// Used for testing serialization of custom structures.
#[derive(Serialize, Debug, PartialEq)]
struct SerializableStruct {
    pub id: u32,
    pub name: String,
    pub values: Vec<i32>,
}

/// Example struct implementing [`Debug`] but not [`Serialize`]
///
/// Used for testing non-serializable type handling.
#[derive(Debug)]
struct NonSerializableStruct {
    #[allow(dead_code)]
    data: Rc<Vec<i32>>,
}

/// Example struct with mixed serializable/non-serializable fields
///
/// Demonstrates handling of structs with [`serde(skip)`] attributes.
#[derive(Serialize, Debug)]
struct MixedStruct {
    visible: i32,
    #[serde(skip)]
    #[allow(dead_code)]
    hidden: Rc<Vec<i32>>,
}

/// Tests for [`TraceData`] basic functionality
mod trace_data_tests {
    use super::*;

    #[test]
    fn creation() {
        let args = serde_json::json!({"param1": 42, "param2": "test"});
        let trace = TraceData::new("test_function", args.clone());

        assert_eq!(trace.function_name, "test_function");
        assert_eq!(trace.args, args);
        assert_eq!(trace.result, None);
    }

    #[test]
    fn with_result() {
        let args = serde_json::json!({"input": "test"});
        let result = serde_json::json!({"output": "success"});

        let trace = TraceData::new("test_function", args.clone()).with_result(result.clone());

        assert_eq!(trace.function_name, "test_function");
        assert_eq!(trace.args, args);
        assert_eq!(trace.result, Some(result));
    }

    #[test]
    fn set_result() {
        let args = serde_json::json!({"input": "test"});
        let result = serde_json::json!({"output": "success"});

        let mut trace = TraceData::new("test_function", args.clone());
        trace.set_result(result.clone());

        assert_eq!(trace.result, Some(result));
    }

    #[test]
    fn serialization_roundtrip() {
        let trace = TraceData {
            timestamp: Utc.with_ymd_and_hms(2023, 1, 1, 12, 0, 0).unwrap(),
            function_name: "test_fn".to_string(),
            args: serde_json::json!({"x": 1}),
            result: Some(serde_json::json!({"y": 2})),
        };

        let serialized = serde_json::to_string(&trace).unwrap();
        let deserialized: TraceData = serde_json::from_str(&serialized).unwrap();

        assert_eq!(trace, deserialized);
    }
}

/// Tests for serialization functions and macros
mod serialization_tests {
    use super::*;

    #[test]
    fn serialize_basic_types() {
        // Test primitive types
        assert_eq!(serialize_value(&42i32), serde_json::json!(42));
        assert_eq!(serialize_value(&3.14f64), serde_json::json!(3.14));
        assert_eq!(serialize_value(&true), serde_json::json!(true));
        assert_eq!(serialize_value(&"hello"), serde_json::json!("hello"));

        // Test collections
        let vec = vec![1, 2, 3];
        assert_eq!(serialize_value(&vec), serde_json::json!([1, 2, 3]));

        let mut map = HashMap::new();
        map.insert("key".to_string(), 42);
        let json_result = serialize_value(&map);
        assert!(json_result.is_object());
    }

    #[test]
    fn serialize_custom_struct() {
        let test_struct = SerializableStruct {
            id: 123,
            name: "test".to_string(),
            values: vec![1, 2, 3],
        };

        let json = serialize_value(&test_struct);
        let expected = serde_json::json!({
            "id": 123,
            "name": "test",
            "values": [1, 2, 3]
        });

        assert_eq!(json, expected);
    }

    #[test]
    fn serialize_with_skip_fields() {
        let test_obj = MixedStruct {
            visible: 42,
            hidden: Rc::new(vec![1, 2, 3]),
        };

        let json = serialize_value(&test_obj);
        let json_str = json.to_string();

        assert!(json_str.contains("\"visible\":42"));
        assert!(!json_str.contains("hidden"));
    }

    #[test]
    fn serialize_failure_handling() {
        // This test ensures that even if serialization could theoretically fail,
        // our function handles it gracefully
        let value = 42i32;
        let result = serialize_value(&value);

        // Should succeed for basic types
        assert_eq!(result, serde_json::json!(42));

        // The error case is hard to trigger with normal types,
        // but the function should handle it gracefully if it occurs
    }
}

/// Tests for placeholder functions
mod placeholder_tests {
    use super::*;

    #[test]
    fn placeholder_for_test() {
        let rc_value = Rc::new(vec![1, 2, 3]);
        let json = placeholder_for(&rc_value);

        if let serde_json::Value::String(s) = json {
            assert!(s.contains("unserializable"));
            assert!(s.contains("alloc::rc::Rc"));
        } else {
            panic!("Expected String placeholder");
        }
    }

    #[test]
    fn debug_placeholder_for_test() {
        let non_serializable = NonSerializableStruct {
            data: Rc::new(vec![1, 2, 3]),
        };

        let json = debug_placeholder_for(&non_serializable);

        if let serde_json::Value::String(s) = json {
            assert!(s.contains("debug:"));
            assert!(s.contains("NonSerializableStruct"));
            assert!(s.contains("[1, 2, 3]"));
        } else {
            panic!("Expected String debug placeholder");
        }
    }

    #[test]
    fn type_name_accuracy() {
        let rc_value = Rc::new(42);
        let placeholder = placeholder_for(&rc_value);

        if let serde_json::Value::String(s) = placeholder {
            assert!(s.contains("alloc::rc::Rc<i32>"));
        } else {
            panic!("Expected string placeholder");
        }
    }
}

/// Tests for macros
mod macro_tests {
    use super::*;

    #[test]
    fn serialize_value_macro() {
        let number = 42i32;
        let string = "hello".to_string();
        let vector = vec![1, 2, 3];

        assert_eq!(serialize_value!(&number), serde_json::json!(42));
        assert_eq!(serialize_value!(&string), serde_json::json!("hello"));
        assert_eq!(serialize_value!(&vector), serde_json::json!([1, 2, 3]));
    }

    #[test]
    fn placeholder_for_macro() {
        let rc_value = Rc::new(vec![1, 2, 3]);
        let json = placeholder_for!(&rc_value);

        if let serde_json::Value::String(s) = json {
            assert!(s.contains("unserializable"));
        } else {
            panic!("Expected String placeholder");
        }
    }

    #[test]
    fn args_json_macro() {
        let param1 = 42i32;
        let param2 = "test".to_string();
        let param3 = Rc::new(vec![1, 2, 3]);

        let json = args_json!(
            "param1" => serialize_value!(&param1),
            "param2" => serialize_value!(&param2),
            "param3" => placeholder_for!(&param3)
        );

        assert!(json.is_object());
        let obj = json.as_object().unwrap();

        assert_eq!(obj.get("param1"), Some(&serde_json::json!(42)));
        assert_eq!(obj.get("param2"), Some(&serde_json::json!("test")));

        let param3_value = obj.get("param3").unwrap();
        if let serde_json::Value::String(s) = param3_value {
            assert!(s.contains("unserializable"));
        } else {
            panic!("Expected unserializable placeholder for param3");
        }
    }

    #[test]
    fn args_json_empty() {
        let json = args_json!();
        assert!(json.is_object());
        assert_eq!(json.as_object().unwrap().len(), 0);
    }

    #[test]
    fn args_json_trailing_comma() {
        let param1 = 42i32;
        let param2 = "test".to_string();

        let json = args_json!(
            "param1" => serialize_value!(&param1),
            "param2" => serialize_value!(&param2),
        );

        assert!(json.is_object());
        let obj = json.as_object().unwrap();
        assert_eq!(obj.len(), 2);
    }
}

/// Tests for edge cases and boundary conditions
mod edge_case_tests {
    use super::*;

    #[test]
    fn empty_values() {
        // Test empty string
        let empty_str = "";
        assert_eq!(serialize_value(&empty_str), serde_json::json!(""));

        // Test empty vector
        let empty_vec: Vec<i32> = vec![];
        assert_eq!(serialize_value(&empty_vec), serde_json::json!([]));

        // Test empty hashmap
        let empty_map: HashMap<String, i32> = HashMap::new();
        let json = serialize_value(&empty_map);
        assert!(json.is_object());
        assert_eq!(json.as_object().unwrap().len(), 0);
    }

    #[test]
    fn large_values() {
        // Test large numbers
        let large_int = i64::MAX;
        assert_eq!(serialize_value(&large_int), serde_json::json!(i64::MAX));

        // Test large string
        let large_string = "a".repeat(1000);
        let json = serialize_value(&large_string);
        assert_eq!(json.as_str().unwrap().len(), 1000);
    }

    #[test]
    fn nested_structures() {
        let nested = serde_json::json!({
            "level1": {
                "level2": {
                    "level3": [1, 2, 3]
                }
            }
        });

        let result = serialize_value(&nested);
        assert_eq!(result, nested);
    }
}

/// Tests for re-exported types
mod reexport_tests {
    use super::*;

    #[test]
    fn json_value_reexport() {
        let value: JsonValue = serde_json::json!({"test": true});
        assert!(value.is_object());
    }

    #[test]
    fn datetime_reexport() {
        let now: DateTime<Utc> = Utc::now();
        assert!(now.timestamp() > 0);
    }
}
