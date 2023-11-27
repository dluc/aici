use anyhow::Result;
use clap::Parser;

use rllm::{config::SamplingParams, playground_1, LoaderArgs, RllmEngine};

const DEFAULT_PROMPT: &str = "Tarski's fixed-point theorem was proven by";

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// The temperature used to generate samples.
    #[arg(long)]
    temperature: Option<f64>,

    /// Nucleus sampling probability cutoff.
    #[arg(long)]
    top_p: Option<f64>,

    /// The seed to use when generating random samples.
    #[arg(long, default_value_t = 42)]
    seed: u64,

    /// The length of the sample to generate (in tokens).
    #[arg(long, default_value_t = 10)]
    sample_len: usize,

    /// The initial prompt.
    #[arg(long)]
    prompt: Option<String>,

    #[arg(long)]
    model_id: Option<String>,

    #[arg(long)]
    revision: Option<String>,

    #[arg(long, default_value_t = false)]
    reference: bool,

    #[arg(long, default_value_t = 0)]
    alt: usize,

    /// The folder name that contains safetensor weights and json files
    /// (same structure as huggingface online)
    #[arg(long)]
    local_weights: Option<String>,
}

fn main() -> Result<()> {
    let args = Args::parse();

    if args.alt == 3 {
        playground_1();
        return Ok(());
    }

    let mut infer = RllmEngine::load(LoaderArgs {
        model_id: args.model_id,
        revision: args.revision,
        local_weights: args.local_weights,
        use_reference: args.reference,
        alt: args.alt,
    })?;

    let prompt = args.prompt.as_ref().map_or(DEFAULT_PROMPT, |p| p.as_str());

    println!("{prompt}");

    let mut p = SamplingParams::default();
    p.temperature = args.temperature.map_or(p.temperature, |v| v as f32);
    p.top_p = args.top_p.map_or(p.top_p, |v| v as f32);
    p.max_tokens = args.sample_len;

    let start_gen = std::time::Instant::now();
    let gen = infer.generate(prompt, p)?;
    let dt = start_gen.elapsed();
    println!("\n{gen}\ntime: {dt:?}\n");
    Ok(())
}
