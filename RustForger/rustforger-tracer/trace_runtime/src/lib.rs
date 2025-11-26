
#[cfg(feature = "with_macro")]
pub use trace_macro;

// use tracing::{Subscriber, subscriber::set_global_default};
// use tracing_subscriber::{Layer, Registry, layer::SubscriberExt};
// use std::sync::{Arc, Mutex, RwLock};
// use std::collections::HashMap;
// use std::thread;

// --- trace_data module ---
pub mod trace_data {
    use serde::Serialize;
    use serde_json::Value;
    use std::sync::{Arc, Mutex};

    /// Represents a single function call in the call stack
    #[derive(Debug, Serialize)]
    pub struct CallNode {
        pub name: String,
        pub file: String,
        pub line: u32,
        #[serde(serialize_with = "serialize_mutex_vec")]
        pub children: Mutex<Vec<Arc<CallNode>>>,
    }

    impl Clone for CallNode {
        fn clone(&self) -> Self {
            Self {
                name: self.name.clone(),
                file: self.file.clone(),
                line: self.line,
                children: Mutex::new(Vec::new()), 
            }
        }
    }

    fn serialize_mutex_vec<S>(mutex_vec: &Mutex<Vec<Arc<CallNode>>>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeSeq;
        let locked_vec = mutex_vec.lock().unwrap();
        let mut seq = serializer.serialize_seq(Some(locked_vec.len()))?;
        for element in locked_vec.iter() {
            seq.serialize_element(&**element)?;
        }
        seq.end()
    }

    /// Complete trace data for a function call
    #[derive(Debug, Serialize)]
    pub struct CallData {
        pub timestamp_utc: String,
        pub thread_id: String,
        #[serde(serialize_with = "serialize_arc_call_node")]
        pub root_node: Arc<CallNode>,
        pub inputs: Value,
        pub output: Value,
    }

    fn serialize_arc_call_node<S>(arc_node: &Arc<CallNode>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        arc_node.as_ref().serialize(serializer)
    }
}

// --- tracer module ---
pub mod tracer {
    use crate::trace_data::{CallData, CallNode};
    use std::collections::HashMap;
    use std::fs::{File, OpenOptions};
    use std::io::{Write, BufWriter};
    use std::path::{Path, PathBuf};
    use std::sync::{Arc, Mutex};
    use std::thread;

    /// Errors that can occur during tracing operations
    #[derive(Debug)]
    pub enum TraceError {
        Io(std::io::Error),
        Serialization(serde_json::Error),
        LockPoisoned,
        TracingSetup(String),
    }

    impl std::fmt::Display for TraceError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                TraceError::Io(e) => write!(f, "IO error: {}", e),
                TraceError::Serialization(e) => write!(f, "Serialization error: {}", e),
                TraceError::LockPoisoned => write!(f, "Lock was poisoned"),
                TraceError::TracingSetup(e) => write!(f, "Tracing setup error: {}", e),
            }
        }
    }

    impl std::error::Error for TraceError {}

    impl From<std::io::Error> for TraceError {
        fn from(err: std::io::Error) -> Self {
            TraceError::Io(err)
        }
    }

    impl From<serde_json::Error> for TraceError {
        fn from(err: serde_json::Error) -> Self {
            TraceError::Serialization(err)
        }
    }

    /// Output configuration for trace data
    #[derive(Debug, Clone)]
    pub enum OutputMode {
        /// Store in memory, write only on manual finalize
        Memory,
        /// Stream directly to file with automatic cleanup
        Stream { path: PathBuf },
    }

    /// Configuration for auto-save functionality
    #[derive(Debug, Clone)]
    pub struct AutoSaveConfig {
        pub path: PathBuf,
        pub enable_panic_hook: bool,
        pub enable_exit_hook: bool,
    }

    impl Default for AutoSaveConfig {
        fn default() -> Self {
            Self {
                path: Self::default_path(),
                enable_panic_hook: true,
                enable_exit_hook: true,
            }
        }
    }

    impl AutoSaveConfig {
        /// Create new auto-save configuration with specified output path
        pub fn new(path: impl Into<PathBuf>) -> Self {
            Self {
                path: path.into(),
                enable_panic_hook: true,
                enable_exit_hook: true,
            }
        }

        /// Disable panic and exit hooks for this configuration
        pub fn no_hooks(mut self) -> Self {
            self.enable_panic_hook = false;
            self.enable_exit_hook = false;
            self
        }

        /// Generate a reasonable default output path following platform conventions
        fn default_path() -> PathBuf {
            // Priority 1: Explicit environment variable override
            if let Ok(path) = std::env::var("TRACE_OUTPUT_FILE") {
                return PathBuf::from(path);
            }

            // Priority 2: Try to use platform-appropriate directories
            if let Some(data_dir) = Self::get_app_data_dir() {
                return data_dir.join("trace_output.json");
            }

            // Priority 3: Fallback to current working directory
            if let Ok(current_dir) = std::env::current_dir() {
                current_dir.join("trace_output.json")
            } else {
                // Last resort: use system temp directory
                std::env::temp_dir().join("trace_output.json")
            }
        }

        /// Attempt to find an appropriate application data directory
        fn get_app_data_dir() -> Option<PathBuf> {
            #[cfg(target_os = "windows")]
            {
                std::env::var("APPDATA")
                    .ok()
                    .map(|appdata| PathBuf::from(appdata).join("rust-tracer"))
            }

            #[cfg(target_os = "macos")]
            {
                std::env::var("HOME")
                    .ok()
                    .map(|home| PathBuf::from(home)
                        .join("Library")
                        .join("Application Support")
                        .join("rust-tracer"))
            }

            #[cfg(target_os = "linux")]
            {
                // Follow XDG Base Directory Specification
                if let Ok(xdg_data_home) = std::env::var("XDG_DATA_HOME") {
                    Some(PathBuf::from(xdg_data_home).join("rust-tracer"))
                } else if let Ok(home) = std::env::var("HOME") {
                    Some(PathBuf::from(home).join(".local").join("share").join("rust-tracer"))
                } else {
                    None
                }
            }

            #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
            {
                // For other Unix-like systems, try HOME/.rust-tracer
                std::env::var("HOME")
                    .ok()
                    .map(|home| PathBuf::from(home).join(".rust-tracer"))
            }
        }

        /// Create an auto-save configuration that attempts to create the directory
        /// structure if it doesn't exist, with graceful fallback behavior
        pub fn with_directory_creation() -> Self {
            let path = Self::default_path();
            
            // Attempt to create parent directories
            if let Some(parent) = path.parent() {
                if let Err(_) = std::fs::create_dir_all(parent) {
                    // If we can't create the preferred directory, fall back to current dir
                    return Self::new("trace_output.json");
                }
            }
            
            Self::new(path)
        }
    }

    #[derive(Debug)]
    struct TracerState {
        call_stacks: HashMap<thread::ThreadId, Vec<Arc<CallNode>>>,
        results: Vec<CallData>,
        output_mode: OutputMode,
        stream_writer: Option<BufWriter<File>>,
        tracing_initialized: bool,
        stream_event_count: usize, 
    }

    impl TracerState {
        fn new() -> Self {
            TracerState {
                call_stacks: HashMap::new(),
                results: Vec::new(),
                output_mode: OutputMode::Memory,
                stream_writer: None,
                tracing_initialized: false,
                stream_event_count: 0,
            }
        }

        fn ensure_tracing_initialized(&mut self) -> Result<(), TraceError> {
            if !self.tracing_initialized {
                self.tracing_initialized = true;
            }
            Ok(())
        }

        fn set_output_mode(&mut self, mode: OutputMode) -> Result<(), TraceError> {
            if let Some(mut writer) = self.stream_writer.take() {
                let _ = writeln!(writer, "");
                let _ = writeln!(writer, "]");
                let _ = writer.flush();
            }
            
            match &mode {
                OutputMode::Memory => {
                    self.stream_writer = None;
                }
                OutputMode::Stream { path } => {
                    if let Some(parent) = path.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    let file = OpenOptions::new()
                        .create(true)
                        .write(true)
                        .truncate(true)
                        .open(path)?;
                    let mut writer = BufWriter::new(file);
                    writeln!(writer, "[")?;
                    writer.flush()?;
                    self.stream_writer = Some(writer);
                    self.stream_event_count = 0; 
                }
            }
            
            self.output_mode = mode;
            Ok(())
        }

        fn write_stream_event(&mut self, call_data: &CallData) -> Result<(), TraceError> {
            if let Some(writer) = &mut self.stream_writer {
                if self.stream_event_count > 0 {
                    writeln!(writer, ",")?;
                }
                let json_string = serde_json::to_string_pretty(call_data)?;
                write!(writer, "{}", json_string)?;
                writer.flush()?;
                self.stream_event_count += 1;
            }
            Ok(())
        }

        fn finalize_to_path(&mut self, output_path: &Path) -> Result<(), TraceError> {
            match &self.output_mode {
                OutputMode::Memory => {
                    if let Some(parent) = output_path.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    let json_string = serde_json::to_string_pretty(&self.results)?;
                    let mut file = File::create(output_path)?;
                    file.write_all(json_string.as_bytes())?;
                    file.flush()?;
                },
                OutputMode::Stream { path: stream_path } => {
                    if let Some(mut writer) = self.stream_writer.take() {
                        writeln!(writer, "")?;
                        writeln!(writer, "]")?;
                        writer.flush()?;
                        
                        if output_path != stream_path {
                            std::fs::copy(stream_path, output_path)?;
                        }
                    }
                }
            }
            
            self.results.clear();
            Ok(())
        }

        fn emergency_save(&mut self) -> Result<(), TraceError> {
            match &self.output_mode {
                OutputMode::Stream { .. } => {
                    if let Some(mut writer) = self.stream_writer.take() {
                        let _ = writeln!(writer, "");
                        let _ = writeln!(writer, "]");
                        let _ = writer.flush();
                    }
                },
                OutputMode::Memory => {
                    if !self.results.is_empty() {
                        let emergency_path = "emergency_trace_backup.json";
                        let json_string = serde_json::to_string_pretty(&self.results)?;
                        let mut file = File::create(emergency_path)?;
                        file.write_all(json_string.as_bytes())?;
                        file.flush()?;
                    }
                }
            }
            Ok(())
        }
    }

    lazy_static::lazy_static! {
        static ref TRACER: Mutex<TracerState> = Mutex::new(TracerState::new());
    }

    /// Public interface for tracing operations
    pub mod interface {
        use super::*;
        use serde_json::Value;

        pub use super::{TraceError, OutputMode, AutoSaveConfig};

        /// Initialize tracing system (should be called once at startup)
        pub fn init() -> Result<(), TraceError> {
            let mut state = TRACER.lock().map_err(|_| TraceError::LockPoisoned)?;
            state.ensure_tracing_initialized()
        }

        /// Enter a function call (static function name)
        pub fn enter(fn_name: &'static str, file: &'static str, line: u32) {
            let _ = init();
        
            tracing::info!(
                target: "rustforger_trace",
                "Entering function: {} at {}:{}",
                fn_name, file, line
            );
            
            if let Ok(mut state) = TRACER.lock() {
                let thread_id = thread::current().id();
                let stack = state.call_stacks.entry(thread_id).or_default();
                
                let node = Arc::new(CallNode {
                    name: fn_name.to_string(),
                    file: file.to_string(),
                    line,
                    children: Mutex::new(Vec::new()),
                });
                
                if let Some(parent) = stack.last() {
                    if let Ok(mut children) = parent.children.lock() {
                        children.push(node.clone());
                    }
                }
                
                stack.push(node);
            }
        }

        /// Enter a function call (dynamic function name)
        pub fn enter_dynamic(fn_name: &str, file: &'static str, line: u32) {
            let _ = init();
            
            tracing::info!(
                target: "rustforger_trace",
                "Entering function: {} at {}:{}",
                fn_name, file, line
            );
            
            if let Ok(mut state) = TRACER.lock() {
                let thread_id = thread::current().id();
                let stack = state.call_stacks.entry(thread_id).or_default();
                
                let node = Arc::new(CallNode {
                    name: fn_name.to_string(),
                    file: file.to_string(),
                    line,
                    children: Mutex::new(Vec::new()),
                });
                
                if let Some(parent) = stack.last() {
                    if let Ok(mut children) = parent.children.lock() {
                        children.push(node.clone());
                    }
                }
                
                stack.push(node);
            }
        }

        /// Exit the current function call
        pub fn exit() {
            tracing::info!(target: "rustforger_trace", "Exiting function");
            
            if let Ok(mut state) = TRACER.lock() {
                let thread_id = thread::current().id();
                if let Some(stack) = state.call_stacks.get_mut(&thread_id) {
                    stack.pop();
                }
            }
        }

        pub fn record_function_call(inputs: Value, output: Value) {
            tracing::info!(
                target: "rustforger_trace",
                "Recording function call with inputs: {:?}, output: {:?}",
                inputs, output
            );
            
            if let Ok(mut state) = TRACER.lock() {
                let thread_id = thread::current().id();

                let should_record = if let Some(stack) = state.call_stacks.get(&thread_id) {
                    !stack.is_empty()
                } else {
                    false
                };

                if should_record {
                    let current_node_option = if let Some(stack) = state.call_stacks.get(&thread_id) {
                        stack.last().cloned()
                    } else {
                        None
                    };

                    if let Some(current_node) = current_node_option {
                        let call_data = CallData {
                            timestamp_utc: chrono::Utc::now().to_rfc3339(),
                            thread_id: format!("{:?}", thread_id),
                            root_node: current_node,
                            inputs,
                            output,
                        };

                        match &state.output_mode {
                            OutputMode::Memory => {
                                state.results.push(call_data);
                            },
                            OutputMode::Stream { .. } => {
                                if state.write_stream_event(&call_data).is_err() {
                                    // Fallback to memory on stream error
                                    state.results.push(call_data);
                                }
                            }
                        }
                    }
                }
            }
        }

        /// Record a complete top-level function call
        pub fn record_top_level_call(inputs: Value, output: Value) {
            record_function_call(inputs, output);
        }

        /// Enable auto-save with robust configuration
        pub fn enable_auto_save(config: AutoSaveConfig) -> Result<(), TraceError> {
            {
                let mut state = TRACER.lock().map_err(|_| TraceError::LockPoisoned)?;
                state.set_output_mode(OutputMode::Stream { path: config.path.clone() })?;
            }

            if config.enable_panic_hook {
                let original_hook = std::panic::take_hook();
                std::panic::set_hook(Box::new(move |panic_info| {
                    let _ = emergency_save();
                    original_hook(panic_info);
                }));
            }

            if config.enable_exit_hook {
                #[cfg(unix)]
                unsafe {
                    extern "C" fn exit_handler() {
                        let _ = emergency_save();
                    }
                    libc::atexit(exit_handler);
                }
            }

            Ok(())
        }

        /// Emergency save for panic/exit situations
        fn emergency_save() -> Result<(), TraceError> {
            if let Ok(mut state) = TRACER.try_lock() {
                state.emergency_save()
            } else {
                Ok(())
            }
        }

        /// Finalize and write trace data to specified path
        pub fn finalize(output_path: &Path) -> Result<(), TraceError> {
            let mut state = TRACER.lock().map_err(|_| TraceError::LockPoisoned)?;
            state.finalize_to_path(output_path)
        }

        /// Get current tracing statistics
        pub fn get_stats() -> Result<(usize, usize), TraceError> {
            let state = TRACER.lock().map_err(|_| TraceError::LockPoisoned)?;
            let total_events = state.results.len();
            let active_threads = state.call_stacks.len();
            Ok((total_events, active_threads))
        }

        /// Clear all trace data (useful for testing)
        pub fn clear() -> Result<(), TraceError> {
            let mut state = TRACER.lock().map_err(|_| TraceError::LockPoisoned)?;
            
            if let Some(mut writer) = state.stream_writer.take() {
                let _ = writeln!(writer, "]");
                let _ = writer.flush();
            }
            
            state.results.clear();
            state.call_stacks.clear();
            state.output_mode = OutputMode::Memory;
            state.stream_event_count = 0; 
            
            Ok(())
        }

        /// Enable auto-save with intelligent defaults
        pub fn enable_auto_save_default() -> Result<(), TraceError> {
            let config = AutoSaveConfig::with_directory_creation();
            enable_auto_save(config)
        }

        /// Enable auto-save with explicit output path
        pub fn enable_auto_save_with_path<P: AsRef<Path>>(output_path: P) -> Result<(), TraceError> {
            let path = output_path.as_ref();
            
            // Ensure parent directory exists
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).map_err(TraceError::Io)?;
            }
            
            let config = AutoSaveConfig::new(path);
            enable_auto_save(config)
        }

        /// Ensure auto-save is initialized (called from macro-generated code)
        pub fn ensure_auto_save_initialized() {
            use std::sync::Once;
            static AUTO_SAVE_INIT: Once = Once::new();
            AUTO_SAVE_INIT.call_once(|| {
                let _ = enable_auto_save_default();
            });
        }
    }
}