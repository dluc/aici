#!/bin/sh

set -e
set -x

MODEL=NousResearch/Llama-2-7b-chat-hf
TOK=llama

#MODEL=codellama/CodeLlama-34b-Instruct-hf
MODEL=codellama/CodeLlama-13b-Instruct-hf
TOK=codellama

(cd aicirt && cargo build --release)

RUST_LOG=info \
PYTHONPATH=.:vllm \
python harness/vllm_server.py \
    --aici-rt ./aicirt/target/release/aicirt \
    --aici-tokenizer $TOK \
    --aici-trace tmp/trace.jsonl \
    --model $MODEL \
    --tokenizer hf-internal-testing/llama-tokenizer \
    --port 8080 --host 127.0.0.1