#!/usr/bin/env python3
import argparse
import sys

from rossum_agent.agent import create_agent
from rossum_agent.example_prompts import PROMPTS
from rossum_agent.utils import check_env_vars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardcoded-prompt", type=str, choices=PROMPTS.keys())
    parser.add_argument("--stream-outputs", action="store_true")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    """Main entry point - run interactive agent CLI."""
    print("🤖 Rossum Invoice Processing Agent")
    print("=" * 50)

    if missing_vars := check_env_vars():
        print("❌ Missing required environment variables:\n")
        for var, description in missing_vars:
            print(f"  {var}: {description}")
            print(f"  Set with: export {var}=<value>\n")
        sys.exit(1)

    print("\n🔧 Initializing agent...")
    agent = create_agent(args.stream_outputs)

    print("\n" + "=" * 50)
    print("Agent ready! You can now give instructions.")
    print("Example: 'Upload all invoices from the data folder'")
    print("Type 'quit' to exit")
    print("=" * 50 + "\n")

    if args.hardcoded_prompt:
        agent.run(PROMPTS[args.hardcoded_prompt])

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if not user_input:
                continue

            response = agent.run(user_input)
            print(f"\n🤖 Agent: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e!s}\n")


if __name__ == "__main__":
    main(parse_args())
