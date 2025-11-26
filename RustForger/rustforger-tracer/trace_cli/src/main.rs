use clap::{Parser, Subcommand};
use anyhow::{Context, Result};
use std::path::PathBuf;

mod commands;
mod utils;

use commands::{instrument, revert, list_traced, setup, clean, run_flow};
use utils::config::PropagationConfig;

#[derive(Parser)]
#[command(name = "trace_cli")]
#[command(about = "A CLI tool for managing Rust function tracing instrumentation")]
#[command(version = "1.0.0")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Add tracing instrumentation to a specific function
    Instrument {
        /// Path to the Rust source file
        #[arg(short, long)]
        file: PathBuf,
        
        /// Name(s) of the function(s) to instrument (ignored when --all is used)
        #[arg(short = 'n', long)]
        function: Vec<String>,
        
        /// Instrument all functions in the file
        #[arg(long, conflicts_with = "function")]
        all: bool,
        
        /// Path for trace output file
        #[arg(short, long)]
        trace_output: Option<PathBuf>,
        
        /// Enable propagation instrumentation (auto-trace internal calls)
        #[arg(short = 'P', long)]
        propagate: bool,
        
        /// Maximum depth for propagation instrumentation
        #[arg(long, requires = "propagate")]
        max_depth: Option<u32>,
        
        /// Exclude patterns for propagation (e.g., "std::")
        #[arg(long, requires = "propagate")]
        exclude: Vec<String>,
        
        /// Only trace user code (not standard library)
        #[arg(long, requires = "propagate")]
        user_code_only: bool,
    },
    
    /// Remove all tracing instrumentation from files
    Revert {
        /// Path to file or directory to process
        path: PathBuf,
    },
    
    /// List all files containing trace macros
    ListTraced {
        /// Directory to search in (default: current directory)
        #[arg(short, long, default_value = ".")]
        dir: PathBuf,
        
        /// Show detailed information including line numbers
        #[arg(short, long)]
        verbose: bool,
    },
    
    /// Setup tracing dependencies for a project
    Setup {
        /// Project directory (default: current directory)
        #[arg(short = 'd', long, default_value = ".")]
        project_dir: PathBuf,
        
        /// Path to the trace tool root directory
        #[arg(short, long)]
        trace_tool_path: Option<PathBuf>,
        
        /// Force overwrite existing dependencies
        #[arg(short, long)]
        force: bool,
        
        /// Custom trace output file path
        #[arg(short = 'o', long)]
        trace_output: Option<PathBuf>,
        
        /// Enable propagation instrumentation by default
        #[arg(short = 'P', long)]
        propagate: bool,
    },
    
    /// Clean all tracing instrumentation and remove dependencies
    Clean {
        /// Project directory (default: current directory)
        #[arg(short = 'd', long, default_value = ".")]
        project_dir: PathBuf,
    },
    
    /// Execute complete trace flow: setup, instrument, run, and optionally clean
    RunFlow {
        /// Test project directory (where the main executable runs)
        #[arg(long)]
        test_project: PathBuf,
        
        /// Target project directories to instrument (can be multiple)
        #[arg(long)]
        target_project: Vec<PathBuf>,
        
        /// Instrumentation specifications: "file_path:function1,function2"
        #[arg(long)]
        instrument: Vec<String>,
        
        /// Output trace file path
        #[arg(short, long)]
        output: PathBuf,
        
        /// Command to execute after instrumentation
        #[arg(long)]
        exec: String,
        
        /// Clean up after execution
        #[arg(long)]
        clean: bool,
        
        /// Path to the trace tool root directory
        #[arg(short, long)]
        trace_tool_path: Option<PathBuf>,
        
        /// Force overwrite existing configurations
        #[arg(short, long)]
        force: bool,
        
        /// Enable propagation instrumentation
        #[arg(short = 'P', long)]
        propagate: bool,
        
        /// Maximum depth for propagation
        #[arg(long, requires = "propagate")]
        max_depth: Option<u32>,
        
        /// Exclude patterns for propagation
        #[arg(long, requires = "propagate")]
        exclude: Vec<String>,
        
        /// Only trace user code
        #[arg(long, requires = "propagate")]
        user_code_only: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Instrument { 
            file, 
            function, 
            all,
            trace_output, 
            propagate, 
            max_depth, 
            exclude, 
            user_code_only 
        } => {
            // Validate arguments
            if !all && function.is_empty() {
                anyhow::bail!("Either --function or --all must be specified");
            }
            
            let propagation_config = if propagate {
                Some(PropagationConfig {
                    enabled: true,
                    max_depth,
                    exclude_patterns: exclude,
                    user_code_only,
                })
            } else {
                None
            };
            
            if all {
                instrument::run_all(&file, trace_output.as_deref(), propagation_config)
                    .with_context(|| format!("Failed to instrument all functions in file: {}", 
                                            file.display()))?;
            } else {
                instrument::run_multiple(&file, &function, trace_output.as_deref(), propagation_config)
                    .with_context(|| format!("Failed to instrument functions {:?} in file: {}", 
                                            function, file.display()))?;
            }
        }
        
        Commands::Revert { path } => {
            revert::run(&path)
                .with_context(|| format!("Failed to revert tracing in: {}", path.display()))?;
        }
        
        Commands::ListTraced { dir, verbose } => {
            list_traced::run(&dir, verbose)
                .with_context(|| format!("Failed to list traced files in: {}", dir.display()))?;
        }
        
        Commands::Setup { 
            project_dir, 
            trace_tool_path, 
            force, 
            trace_output, 
            propagate 
        } => {
            setup::run(
                &project_dir, 
                trace_tool_path.as_deref(), 
                force, 
                trace_output.as_deref(), 
                propagate
            ).with_context(|| format!("Failed to setup tracing for project: {}", 
                                    project_dir.display()))?;
        }
        
        Commands::Clean { project_dir } => {
            clean::run(&project_dir)
                .with_context(|| format!("Failed to clean tracing for project: {}", 
                                        project_dir.display()))?;
        }
        
        Commands::RunFlow {
            test_project,
            target_project,
            instrument,
            output,
            exec,
            clean,
            force,
            propagate,
            max_depth,
            exclude,
            user_code_only,
            trace_tool_path,
        } => {
            run_flow::run(
                &test_project,
                &target_project,
                &instrument,
                &output,
                &exec,
                clean,
                force,
                propagate,
                max_depth,
                &exclude,
                user_code_only,
                trace_tool_path.as_deref(),
            ).with_context(|| "Failed to execute trace flow")?;
        }
    }
    
    Ok(())
} 