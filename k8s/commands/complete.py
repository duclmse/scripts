"""
Complete Command - Generate shell completions for bash/zsh/fish
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors


@Command.register("complete", help="Generate shell completions", args=[
    arg("shell", nargs="?", choices=["bash", "zsh", "fish", "powershell"],
        help="Shell type (auto-detect if not specified)"),
    arg("--install", action="store_true",
        help="Install completions automatically"),
    arg("--output", help="Output file path"),
    arg("--script-name", default="k8s-mgr", help="Script name for completions"),
])
class CompleteCommand:
    """Generate dynamic shell completions with resource name completion"""

    def __init__(self, kube):
        self.kube = kube
        self.script_name = "k8s-mgr"

    def execute(self, args):
        """Execute completion generation"""
        self.script_name = args.script_name

        # Detect shell if not specified
        shell = args.shell or self.detect_shell()

        if not shell:
            Logger.error(
                "Could not detect shell. Specify explicitly with: complete bash|zsh|fish")
            return

        Logger.info(f"Generating {shell} completions...")

        # Generate completion script
        if shell == "bash":
            script = self.generate_bash_completion()
        elif shell == "zsh":
            script = self.generate_zsh_completion()
        elif shell == "fish":
            script = self.generate_fish_completion()
        elif shell == "powershell":
            script = self.generate_powershell_completion()
        else:
            Logger.error(f"Unsupported shell: {shell}")
            return

        # Output or install
        if args.install:
            self.install_completion(shell, script)
        elif args.output:
            Path(args.output).write_text(script)
            Logger.success(f"Completion script saved to {args.output}")
            self.show_manual_install_instructions(shell, args.output)
        else:
            print(script)
            print(f"\n{Colors.YELLOW}# To install, run:{Colors.RESET}")
            print(f"  {self.script_name} complete {shell} --install")

    def detect_shell(self) -> str | None:
        """Detect current shell"""
        import os
        shell = os.environ.get('SHELL', '')

        if 'bash' in shell:
            return 'bash'
        elif 'zsh' in shell:
            return 'zsh'
        elif 'fish' in shell:
            return 'fish'

        return None

    def generate_bash_completion(self) -> str:
        """Generate bash completion script"""
        return f'''# Bash completion for {self.script_name}
# Source this file or add to ~/.bashrc

_{self.script_name}_completion() {{
    local cur prev words cword
    _init_completion || return

    # Main commands
    local commands="logs logs-all logs-grep logs-merge status delete exec debug \\
        port-forward top scale rollout events tree backup diff watch apply \\
        context describe list get shell-all history cost ports template deps \\
        health doctor secrets jobs compare complete restart validate size \\
        netdebug clone interactive fav bulk git-deploy watch-alert snippet help"

    # Handle subcommands
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return
    fi

    local cmd="${{words[1]}}"

    # Global options
    local global_opts="-v --verbose -n --namespace -o --output -c --context \\
        --no-color -a --app"

    # Command-specific completions
    case "$cmd" in
        logs|logs-grep|exec|delete|describe|debug)
            # Complete pod names dynamically
            if [[ "$cur" != -* ]]; then
                local namespace="${{COMP_NAMESPACE:-default}}"
                local pods=$(kubectl get pods -n "$namespace" -o jsonpath='{{.items[*].metadata.name}}' 2>/dev/null)
                COMPREPLY=( $(compgen -W "$pods" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "$global_opts -f --follow -t --tail --since" -- "$cur") )
            fi
            ;;
        
        status|list|get)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$global_opts -t --type -l --selector -w --watch" -- "$cur") )
            else
                # Complete resource types
                local types="pods deployments services configmaps secrets ingresses"
                COMPREPLY=( $(compgen -W "$types" -- "$cur") )
            fi
            ;;
        
        scale)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$global_opts --replicas -t --type" -- "$cur") )
            else
                # Complete deployment names
                local namespace="${{COMP_NAMESPACE:-default}}"
                local deployments=$(kubectl get deployments -n "$namespace" -o jsonpath='{{.items[*].metadata.name}}' 2>/dev/null)
                COMPREPLY=( $(compgen -W "$deployments" -- "$cur") )
            fi
            ;;
        
        context)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "list use current bookmark" -- "$cur") )
            elif [[ $cword -eq 3 ]] && [[ "${{words[2]}}" == "use" ]]; then
                # Complete context names
                local contexts=$(kubectl config get-contexts -o name 2>/dev/null)
                COMPREPLY=( $(compgen -W "$contexts" -- "$cur") )
            elif [[ $cword -eq 3 ]] && [[ "${{words[2]}}" == "bookmark" ]]; then
                COMPREPLY=( $(compgen -W "add list use delete" -- "$cur") )
            fi
            ;;
        
        fav)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "add list run delete" -- "$cur") )
            elif [[ $cword -eq 3 ]] && [[ "${{words[2]}}" == "run" || "${{words[2]}}" == "delete" ]]; then
                # Complete favorite names from config
                local fav_file="$HOME/.kube-mgr/favorites.json"
                if [[ -f "$fav_file" ]]; then
                    local favs=$(python3 -c "import json; print(' '.join(json.load(open('$fav_file')).keys()))" 2>/dev/null)
                    COMPREPLY=( $(compgen -W "$favs" -- "$cur") )
                fi
            fi
            ;;
        
        bulk)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "delete restart scale label annotate exec logs describe patch" -- "$cur") )
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$global_opts -l --selector -t --type --dry-run --confirm --parallel --delay" -- "$cur") )
            fi
            ;;
        
        compare)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$global_opts --contexts --namespaces --from-context --to-context" -- "$cur") )
            else
                # Complete resource types
                local types="deployment service configmap secret ingress"
                COMPREPLY=( $(compgen -W "$types" -- "$cur") )
            fi
            ;;
        
        *)
            COMPREPLY=( $(compgen -W "$global_opts" -- "$cur") )
            ;;
    esac
}}

complete -F _{self.script_name}_completion {self.script_name}

# Export namespace for dynamic completion
export COMP_NAMESPACE="${{KUBECTL_NAMESPACE:-default}}"
'''

    def generate_zsh_completion(self) -> str:
        """Generate zsh completion script"""
        return f'''#compdef {self.script_name}
# Zsh completion for {self.script_name}

_{self.script_name}() {{
    local -a commands
    local curcontext="$curcontext" state line
    typeset -A opt_args

    commands=(
        'logs:View pod logs'
        'logs-all:Tail logs from multiple pods'
        'logs-grep:Search logs with pattern'
        'logs-merge:Merge logs from multiple pods'
        'status:Check resource status'
        'delete:Delete resources'
        'exec:Execute command in pod'
        'debug:Debug pod with ephemeral container'
        'port-forward:Manage port forwarding'
        'top:Show resource usage'
        'scale:Scale deployments'
        'rollout:Manage rollouts'
        'events:Watch cluster events'
        'tree:Show resource hierarchy'
        'backup:Backup resources'
        'diff:Compare resources'
        'watch:Watch resource changes'
        'apply:Apply configuration'
        'context:Manage contexts'
        'describe:Describe resources'
        'list:List resources'
        'get:Quick get resource'
        'shell-all:Open tmux with multiple shells'
        'history:Resource change history'
        'cost:Resource cost estimation'
        'ports:Port forward manager'
        'template:Manage templates'
        'deps:Show dependencies'
        'health:Health dashboard'
        'doctor:Diagnose issues'
        'secrets:Manage secrets'
        'jobs:Manage jobs'
        'compare:Compare across environments'
        'complete:Generate completions'
        'restart:Smart restart'
        'validate:Validate manifests'
        'size:Analyze resource sizes'
        'netdebug:Network debugging'
        'clone:Clone resources'
        'interactive:Interactive TUI'
        'fav:Manage favorites'
        'bulk:Bulk operations'
        'git-deploy:Deploy from git'
        'watch-alert:Watch and alert'
        'snippet:YAML snippets'
        'help:Show help'
    )

    _arguments -C \\
        '(-v --verbose){{-v,--verbose}}[Enable verbose output]' \\
        '(-n --namespace){{-n,--namespace}}[Kubernetes namespace]:namespace:_k8s_namespaces' \\
        '(-o --output){{-o,--output}}[Output format]:format:(text json yaml wide)' \\
        '(-c --context){{-c,--context}}[Kubernetes context]:context:_k8s_contexts' \\
        '(-a --app){{-a,--app}}[App label]:label:' \\
        '--no-color[Disable colored output]' \\
        '1: :->command' \\
        '*::arg:->args'

    case $state in
        command)
            _describe -t commands 'command' commands
            ;;
        args)
            case $words[1] in
                logs|logs-grep|exec|delete|describe|debug)
                    _arguments \\
                        '*:pod:_k8s_pods' \\
                        '(-f --follow){{-f,--follow}}[Follow logs]' \\
                        '(-t --tail){{-t,--tail}}[Lines to show]:lines:'
                    ;;
                scale)
                    _arguments \\
                        '*:deployment:_k8s_deployments' \\
                        '--replicas[Number of replicas]:replicas:'
                    ;;
                context)
                    _arguments \\
                        '1:action:(list use current bookmark)' \\
                        '*:context:_k8s_contexts'
                    ;;
                fav)
                    _arguments \\
                        '1:action:(add list run delete)' \\
                        '*:favorite:_k8s_mgr_favorites'
                    ;;
                bulk)
                    _arguments \\
                        '1:action:(delete restart scale label annotate exec logs describe patch)' \\
                        '(-l --selector){{-l,--selector}}[Label selector]:selector:' \\
                        '--dry-run[Dry run mode]'
                    ;;
            esac
            ;;
    esac
}}

# Helper functions for dynamic completion
_k8s_pods() {{
    local namespace="${{opt_args[-n]:-default}}"
    local -a pods
    pods=(${{(f)"$(kubectl get pods -n $namespace -o name 2>/dev/null | sed 's|pod/||')"}})
    _describe 'pod' pods
}}

_k8s_deployments() {{
    local namespace="${{opt_args[-n]:-default}}"
    local -a deployments
    deployments=(${{(f)"$(kubectl get deployments -n $namespace -o name 2>/dev/null | sed 's|deployment/||')"}})
    _describe 'deployment' deployments
}}

_k8s_contexts() {{
    local -a contexts
    contexts=(${{(f)"$(kubectl config get-contexts -o name 2>/dev/null)"}})
    _describe 'context' contexts
}}

_k8s_namespaces() {{
    local -a namespaces
    namespaces=(${{(f)"$(kubectl get namespaces -o name 2>/dev/null | sed 's|namespace/||')"}})
    _describe 'namespace' namespaces
}}

_k8s_mgr_favorites() {{
    local fav_file="$HOME/.kube-mgr/favorites.json"
    if [[ -f "$fav_file" ]]; then
        local -a favs
        favs=(${{(f)"$(python3 -c "import json; print('\\\\n'.join(json.load(open('$fav_file')).keys()))" 2>/dev/null)"}})
        _describe 'favorite' favs
    fi
}}

_{self.script_name} "$@"
'''

    def generate_fish_completion(self) -> str:
        """Generate fish completion script"""
        return f'''# Fish completion for {self.script_name}

# Main commands
complete -c {self.script_name} -f

# Global options
complete -c {self.script_name} -s v -l verbose -d 'Enable verbose output'
complete -c {self.script_name} -s n -l namespace -d 'Kubernetes namespace' -xa '(kubectl get namespaces -o name 2>/dev/null | sed "s|namespace/||")'
complete -c {self.script_name} -s o -l output -d 'Output format' -xa 'text json yaml wide'
complete -c {self.script_name} -s c -l context -d 'Kubernetes context' -xa '(kubectl config get-contexts -o name 2>/dev/null)'
complete -c {self.script_name} -s a -l app -d 'App label'
complete -c {self.script_name} -l no-color -d 'Disable colored output'

# Subcommands
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'logs' -d 'View pod logs'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'logs-all' -d 'Tail logs from multiple pods'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'logs-grep' -d 'Search logs'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'status' -d 'Check status'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'delete' -d 'Delete resources'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'exec' -d 'Execute command'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'debug' -d 'Debug pod'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'port-forward' -d 'Port forwarding'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'top' -d 'Resource usage'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'scale' -d 'Scale resources'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'rollout' -d 'Manage rollouts'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'events' -d 'Watch events'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'tree' -d 'Resource hierarchy'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'context' -d 'Manage contexts'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'fav' -d 'Favorites'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'bulk' -d 'Bulk operations'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'compare' -d 'Compare environments'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'health' -d 'Health dashboard'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'doctor' -d 'Diagnose issues'
complete -c {self.script_name} -n '__fish_use_subcommand' -a 'complete' -d 'Generate completions'

# Pod name completion for commands that need it
complete -c {self.script_name} -n '__fish_seen_subcommand_from logs logs-grep exec delete describe debug' -xa '(kubectl get pods -o name 2>/dev/null | sed "s|pod/||")'

# Deployment name completion
complete -c {self.script_name} -n '__fish_seen_subcommand_from scale rollout' -xa '(kubectl get deployments -o name 2>/dev/null | sed "s|deployment/||")'

# Context subcommand actions
complete -c {self.script_name} -n '__fish_seen_subcommand_from context' -xa 'list use current bookmark'
complete -c {self.script_name} -n '__fish_seen_subcommand_from context; and __fish_seen_subcommand_from use' -xa '(kubectl config get-contexts -o name 2>/dev/null)'
complete -c {self.script_name} -n '__fish_seen_subcommand_from context; and __fish_seen_subcommand_from bookmark' -xa 'add list use delete'

# Favorite subcommand actions
complete -c {self.script_name} -n '__fish_seen_subcommand_from fav' -xa 'add list run delete'

# Bulk subcommand actions
complete -c {self.script_name} -n '__fish_seen_subcommand_from bulk' -xa 'delete restart scale label annotate exec logs describe patch'

# Command-specific options
complete -c {self.script_name} -n '__fish_seen_subcommand_from logs logs-grep' -s f -l follow -d 'Follow logs'
complete -c {self.script_name} -n '__fish_seen_subcommand_from logs logs-grep' -s t -l tail -d 'Lines to show'
complete -c {self.script_name} -n '__fish_seen_subcommand_from scale' -l replicas -d 'Number of replicas'
complete -c {self.script_name} -n '__fish_seen_subcommand_from bulk' -l dry-run -d 'Dry run mode'
complete -c {self.script_name} -n '__fish_seen_subcommand_from bulk' -s l -l selector -d 'Label selector'
'''

    def generate_powershell_completion(self) -> str:
        """Generate PowerShell completion script"""
        return f'''# PowerShell completion for {self.script_name}

Register-ArgumentCompleter -Native -CommandName {self.script_name} -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)

    $commands = @(
        'logs', 'logs-all', 'logs-grep', 'status', 'delete', 'exec', 
        'debug', 'port-forward', 'top', 'scale', 'rollout', 'events',
        'tree', 'backup', 'diff', 'watch', 'apply', 'context', 
        'describe', 'list', 'fav', 'bulk', 'compare', 'health', 
        'doctor', 'complete'
    )

    $globalOpts = @('-v', '--verbose', '-n', '--namespace', '-o', '--output', 
                    '-c', '--context', '-a', '--app', '--no-color')

    # Get all words in command line
    $words = $commandAst.ToString() -split '\\s+'
    
    # If we're completing the first argument (command)
    if ($words.Count -eq 2) {{
        $commands | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }}
        return
    }}

    # Get the subcommand
    $subcommand = $words[1]

    # Complete based on subcommand
    switch ($subcommand) {{
        'logs' {{
            if ($wordToComplete -like '-*') {{
                $globalOpts + @('-f', '--follow', '-t', '--tail') | 
                    Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                    }}
            }} else {{
                # Complete pod names
                $pods = kubectl get pods -o name 2>$null | ForEach-Object {{ $_ -replace 'pod/', '' }}
                $pods | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                }}
            }}
        }}
        
        'scale' {{
            if ($wordToComplete -eq '--replicas') {{
                # No completion for numeric values
            }} elseif ($wordToComplete -like '-*') {{
                $globalOpts + @('--replicas') | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                }}
            }} else {{
                # Complete deployment names
                $deployments = kubectl get deployments -o name 2>$null | ForEach-Object {{ $_ -replace 'deployment/', '' }}
                $deployments | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                }}
            }}
        }}
        
        'context' {{
            if ($words.Count -eq 3) {{
                @('list', 'use', 'current', 'bookmark') | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                }}
            }} elseif ($words[2] -eq 'use') {{
                $contexts = kubectl config get-contexts -o name 2>$null
                $contexts | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                    [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
                }}
            }}
        }}
        
        default {{
            $globalOpts | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
                [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
            }}
        }}
    }}
}}
'''

    def install_completion(self, shell: str, script: str):
        """Install completion script automatically"""
        if shell == "bash":
            self.install_bash(script)
        elif shell == "zsh":
            self.install_zsh(script)
        elif shell == "fish":
            self.install_fish(script)
        elif shell == "powershell":
            self.install_powershell(script)

    def install_bash(self, script: str):
        """Install bash completion"""
        completion_dir = Path.home() / ".bash_completion.d"
        completion_dir.mkdir(exist_ok=True)

        completion_file = completion_dir / f"{self.script_name}"
        completion_file.write_text(script)

        # Add source to .bashrc if not already there
        bashrc = Path.home() / ".bashrc"
        source_line = f"source {completion_file}"

        if bashrc.exists():
            content = bashrc.read_text()
            if source_line not in content:
                with bashrc.open('a') as f:
                    f.write(f"\n# {self.script_name} completion\n")
                    f.write(f"{source_line}\n")

        Logger.success(f"Bash completion installed to {completion_file}")
        print(f"\n{Colors.YELLOW}Reload shell or run:{Colors.RESET}")
        print(f"  source {completion_file}")

    def install_zsh(self, script: str):
        """Install zsh completion"""
        # Try to find zsh completion directory
        completion_dirs = [
            Path.home() / ".zsh" / "completions",
            Path("/usr/local/share/zsh/site-functions"),
            Path.home() / ".oh-my-zsh" / "completions"
        ]

        completion_dir = None
        for dir in completion_dirs:
            if dir.exists() or dir.parent.exists():
                completion_dir = dir
                break

        if not completion_dir:
            completion_dir = Path.home() / ".zsh" / "completions"

        completion_dir.mkdir(parents=True, exist_ok=True)
        completion_file = completion_dir / f"_{self.script_name}"
        completion_file.write_text(script)

        Logger.success(f"Zsh completion installed to {completion_file}")
        print(
            f"\n{Colors.YELLOW}Add to .zshrc if not already present:{Colors.RESET}")
        print(f"  fpath=({completion_dir} $fpath)")
        print(f"  autoload -Uz compinit && compinit")
        print(f"\nThen reload: exec zsh")

    def install_fish(self, script: str):
        """Install fish completion"""
        completion_dir = Path.home() / ".config" / "fish" / "completions"
        completion_dir.mkdir(parents=True, exist_ok=True)

        completion_file = completion_dir / f"{self.script_name}.fish"
        completion_file.write_text(script)

        Logger.success(f"Fish completion installed to {completion_file}")
        print(f"\n{Colors.YELLOW}Completions are automatically loaded{Colors.RESET}")

    def install_powershell(self, script: str):
        """Install PowerShell completion"""
        profile_path = Path.home() / "Documents" / "PowerShell" / \
            "Microsoft.PowerShell_profile.ps1"

        if not profile_path.parent.exists():
            profile_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to profile
        with profile_path.open('a') as f:
            f.write(f"\n# {self.script_name} completion\n")
            f.write(script)

        Logger.success(f"PowerShell completion added to {profile_path}")
        print(f"\n{Colors.YELLOW}Restart PowerShell to activate{Colors.RESET}")

    def show_manual_install_instructions(self, shell: str, output_file: str):
        """Show manual installation instructions"""
        print(f"\n{Colors.BOLD}Manual Installation Instructions:{Colors.RESET}")

        if shell == "bash":
            print(f"  1. Copy to completion directory:")
            print(
                f"     cp {output_file} ~/.bash_completion.d/{self.script_name}")
            print(f"  2. Add to ~/.bashrc:")
            print(f"     source ~/.bash_completion.d/{self.script_name}")
            print(f"  3. Reload: source ~/.bashrc")

        elif shell == "zsh":
            print(f"  1. Copy to completion directory:")
            print(
                f"     cp {output_file} ~/.zsh/completions/_{self.script_name}")
            print(f"  2. Add to ~/.zshrc:")
            print(f"     fpath=(~/.zsh/completions $fpath)")
            print(f"     autoload -Uz compinit && compinit")
            print(f"  3. Reload: exec zsh")

        elif shell == "fish":
            print(f"  1. Copy to completion directory:")
            print(
                f"     cp {output_file} ~/.config/fish/completions/{self.script_name}.fish")
            print(f"  2. Completions are automatically loaded")

        elif shell == "powershell":
            print(f"  1. Add to PowerShell profile:")
            print(f"     notepad $PROFILE")
            print(f"  2. Paste the contents of {output_file}")
            print(f"  3. Restart PowerShell")


# Usage examples
"""
# Auto-detect and print completion script
python k8s-mgr.py complete

# Generate for specific shell
python k8s-mgr.py complete bash
python k8s-mgr.py complete zsh
python k8s-mgr.py complete fish
python k8s-mgr.py complete powershell

# Save to file
python k8s-mgr.py complete bash --output completion.bash

# Auto-install
python k8s-mgr.py complete bash --install
python k8s-mgr.py complete zsh --install

# Custom script name
python k8s-mgr.py complete bash --script-name kmgr --install
"""
