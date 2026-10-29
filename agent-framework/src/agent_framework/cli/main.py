"""Agent Framework unified CLI for environment management, building, and execution."""

import argparse
import importlib
import subprocess
import sys
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from agent_framework.binding.discovery import discover_bindings
from agent_framework.binding.environment import CheckStatus, EnvironmentProvider
from agent_framework.definition.loader import load_agent_definition
from agent_framework.deployment.loader import load_deployment_spec
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization


def _resolve_provider(provider_path: str) -> EnvironmentProvider:
    mod_name, _, cls_name = provider_path.partition(":")
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls()


def _get_providers(spec: Any, workspace: Path) -> dict[str, tuple[EnvironmentProvider, Mapping[str, Any]]]:
    """Find environment providers for all bindings configured in the deployment."""
    providers = {}
    env_cfg = spec.environment
    target = env_cfg.target
    for namespace, binding_cfg in env_cfg.bindings.items():
        try:
            registry = discover_bindings([f"{namespace}.dummy"])
        except Exception:
            try:
                registry = discover_bindings([f"{namespace}.status"])
            except Exception:
                registry = None
        if registry and namespace in registry.packages:
            prov_path = registry.packages[namespace].environment_provider
            if prov_path:
                provider = _resolve_provider(prov_path)
                providers[namespace] = (provider, binding_cfg)
        else:
            # Fallback direct import
            try:
                mod = importlib.import_module(f"agent_binding_{namespace}")
                pkg = getattr(mod, "get_bindings", lambda: None)()
                if pkg and getattr(pkg, "environment_provider", None):
                    provider = _resolve_provider(pkg.environment_provider)
                    providers[namespace] = (provider, binding_cfg)
            except Exception:
                pass
    return providers


def cmd_env_check(args: argparse.Namespace) -> int:
    deployment_path = Path(args.deployment).resolve()
    spec = load_deployment_spec(deployment_path)
    workspace = deployment_path.parent.parent
    providers = _get_providers(spec, workspace)

    if not providers:
        print(f"No environment providers declared for deployment '{deployment_path.name}'.")
        return 0

    all_ready = True
    print(f"Checking environment for target: '{spec.environment.target}'")
    for name, (provider, config) in providers.items():
        result = provider.check(spec.environment.target, config)
        status_label = "[READY]" if result.is_ready else f"[{result.status.upper()}]"
        print(f"  {status_label} {name}: {result.message}")
        if not result.is_ready:
            all_ready = False
            if result.remediation_hint:
                print(f"         Hint: {result.remediation_hint}")
    return 0 if all_ready else 1


def cmd_env_setup(args: argparse.Namespace) -> int:
    deployment_path = Path(args.deployment).resolve()
    spec = load_deployment_spec(deployment_path)
    workspace = deployment_path.parent.parent
    providers = _get_providers(spec, workspace)

    for name, (provider, config) in providers.items():
        print(f"Setting up environment for {name} ({spec.environment.target})...")
        provider.setup(spec.environment.target, config, auto_install=args.auto)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    agent_path = Path(args.agent).resolve()
    output_dir = Path(args.output).resolve() if args.output else agent_path.parent.parent
    print(f"Building agent from '{agent_path}' -> '{output_dir}'...")
    definition = load_agent_definition(agent_path)
    resolved = resolve_agent(definition)
    artifact, _ = write_artifacts(resolved, output_dir)
    write_realization(resolved, output_dir)
    generate_python(artifact.parent)
    print(f"Build complete. Generated API at {artifact.parent / 'python'}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    deployment_path = Path(args.deployment).resolve()
    spec = load_deployment_spec(deployment_path)
    workspace = deployment_path.parent.parent

    target = args.target or spec.environment.target
    run_dir = Path(args.run_dir or spec.environment.run_dir)
    if not run_dir.is_absolute():
        run_dir = workspace / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    providers = _get_providers(spec, workspace)
    print(f"Starting managed mission execution (Target: {target})...")
    print(f"Logs and artifacts: {run_dir}")

    with ExitStack() as stack:
        for name, (provider, config) in providers.items():
            print(f"  Starting {name} environment...")
            session = stack.enter_context(provider.session(target, config, run_dir))
            print(f"  {name} active ({session.metadata})")

        print("\nExecuting mission script...")
        cmd = [sys.executable, str(Path(args.mission).resolve()), "--workspace", str(workspace)]
        proc = subprocess.Popen(cmd)
        try:
            ret = proc.wait()
        except KeyboardInterrupt:
            print("\nAborting mission (Ctrl+C received)...")
            proc.terminate()
            ret = 130

    print(f"\nMission finished with exit code {ret}.")
    flight_log = run_dir / "flight.ulg"
    if flight_log.exists():
        print(f"Flight telemetry log captured: {flight_log}")
    return ret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent", description="Agent Framework CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # env subcommands
    env_parser = subparsers.add_parser("env", help="Environment management")
    env_sub = env_parser.add_subparsers(dest="subcommand", required=True)
    check_p = env_sub.add_parser("check", help="Verify environment dependencies")
    check_p.add_argument("deployment", help="Path to deployment YAML")
    setup_p = env_sub.add_parser("setup", help="Set up environment dependencies")
    setup_p.add_argument("deployment", help="Path to deployment YAML")
    setup_p.add_argument("--auto", action="store_true", help="Attempt automated setup")

    # build
    build_p = subparsers.add_parser("build", help="Compile agent definition to python API")
    build_p.add_argument("agent", help="Path to agent YAML")
    build_p.add_argument("--output", "-o", help="Output directory")

    # run
    run_p = subparsers.add_parser("run", help="Run a mission within managed environment")
    run_p.add_argument("deployment", help="Path to deployment YAML")
    run_p.add_argument("--mission", "-m", required=True, help="Mission python script to run")
    run_p.add_argument("--target", "-t", choices=["simulation", "hardware"], help="Override environment target")
    run_p.add_argument("--run-dir", help="Override artifact run directory")

    args = parser.parse_args(argv)
    if args.command == "env":
        if args.subcommand == "check":
            return cmd_env_check(args)
        elif args.subcommand == "setup":
            return cmd_env_setup(args)
    elif args.command == "build":
        return cmd_build(args)
    elif args.command == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
