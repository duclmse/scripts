#!/usr/bin/env python3

import pathlib
import sys
import os
import re
import json
import shutil
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
import time

# Language to file extension map
LANG_EXT = {
    'kotlin': 'kt',
    'java': 'java',
    'rust': 'rs',
    'bash': 'sh',
    'shell': 'sh',
    'sh': 'sh',
    'javascript': 'js',
    'js': 'js',
    'typescript': 'ts',
    'ts': 'ts',
    'html': 'html',
    'yml': 'yml',
    'yaml': 'yml',
    'python': 'py',
    'py': 'py',
    'ruby': 'rb',
    'go': 'go',
    'cpp': 'cpp',
    'c': 'c',
    'csharp': 'cs',
    'cs': 'cs',
    'php': 'php',
    'swift': 'swift',
    'scala': 'scala',
    'r': 'r',
    'sql': 'sql',
    'dart': 'dart',
    'elixir': 'ex',
    'haskell': 'hs',
    'lua': 'lua',
    'perl': 'pl',
    'markdown': 'md',
    'md': 'md',
    'json': 'json',
    'xml': 'xml',
    'toml': 'toml',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'dockerfile': 'Dockerfile',
    'makefile': 'Makefile',
    'proto': 'proto',
    'graphql': 'graphql',
    'vue': 'vue',
    'svelte': 'svelte',
}

# Language to comment token map
LANG_COMMENT = {
    'kotlin': '//',
    'java': '//',
    'rust': '//',
    'bash': '#',
    'shell': '#',
    'sh': '#',
    'js': '//',
    'javascript': '//',
    'ts': '//',
    'typescript': '//',
    'html': '<!-- -->',
    'yml': '#',
    'yaml': '#',
    'python': '#',
    'py': '#',
    'ruby': '#',
    'go': '//',
    'cpp': '//',
    'c': '//',
    'csharp': '//',
    'cs': '//',
    'php': '//',
    'swift': '//',
    'scala': '//',
    'r': '#',
    'sql': '--',
    'dart': '//',
    'elixir': '#',
    'haskell': '--',
    'lua': '--',
    'perl': '#',
    'css': '/* */',
    'scss': '//',
}

# Alternative comment patterns for filename detection
FILENAME_PATTERNS = [
    r'^\s*(?:#+|//|<!--|--)\s*(?:File|file|FILE|filename|FILENAME|@file):\s*([^\s]+)',
    r'^\s*(?:#+|//|<!--|--)\s*\[([^\]]+\.[a-z]+)\]',
    r'^\s*<!--\s*([^\s]+)\s*-->',
]


class CodeBlock:
    """Represents an extracted code block"""

    def __init__(self, number: int, language: str, content: List[str],
                 line_start: int, line_end: int, source_file: str,
                 preceding_heading: Optional[str] = None):
        self.number = number
        self.language = language
        self.content = content
        self.line_start = line_start
        self.line_end = line_end
        self.source_file = source_file
        self.filename = None
        self.attributes = {}
        self.preceding_heading = preceding_heading

    def get_hash(self) -> str:
        """Generate hash of content for diff detection"""
        content_str = '\n'.join(self.content)
        return hashlib.md5(content_str.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'number': self.number,
            'language': self.language,
            'filename': self.filename,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'source_file': self.source_file,
            'size': len('\n'.join(self.content)),
            'lines': len(self.content),
            'hash': self.get_hash(),
            'attributes': self.attributes,
            'preceding_heading': self.preceding_heading,
        }


class CodeExtractor:
    """Main code extraction engine"""

    def __init__(self, args):
        self.args = args
        self.blocks: List[CodeBlock] = []
        self.stats = {
            'total_blocks': 0,
            'languages': {},
            'files_created': 0,
            'files_skipped': 0,
            'errors': [],
        }

    def extract_from_file(self, input_file: str) -> List[CodeBlock]:
        """Extract code blocks from a single markdown file"""
        blocks = []
        in_block = False
        block_number = 0
        current_block = None
        line_number = 0
        last_heading = None  # Track the last heading before a code block

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line_number += 1
                    line_stripped = line.rstrip('\n')

                    # Detect markdown headings (# Heading or ## Heading, etc.)
                    if not in_block:
                        heading_match = re.match(
                            r'^(#{1,6})\s+(.+)$', line_stripped)
                        if heading_match:
                            last_heading = heading_match.group(2).strip()
                            continue

                    # Detect code block start
                    if line_stripped.startswith('```'):
                        if not in_block:
                            # Start of code block
                            in_block = True
                            block_number += 1
                            lang_info = line_stripped[3:].strip()

                            # Parse language and attributes (e.g., ```python {filename="app.py"})
                            lang, attributes = self._parse_language_line(
                                lang_info)

                            current_block = CodeBlock(
                                number=block_number,
                                language=lang,
                                content=[],
                                line_start=line_number,
                                line_end=line_number,
                                source_file=input_file,
                                preceding_heading=last_heading
                            )
                            current_block.attributes = attributes
                            # Reset heading after capturing it
                            last_heading = None
                        else:
                            # End of code block
                            in_block = False
                            if current_block:
                                current_block.line_end = line_number
                                blocks.append(current_block)
                                current_block = None
                        continue

                    # Collect block content
                    if in_block and current_block:
                        current_block.content.append(line_stripped)

        except Exception as e:
            self.stats['errors'].append(
                f"Error reading {input_file}: {str(e)}")
            if not self.args.continue_on_error:
                raise

        return blocks

    def _parse_language_line(self, lang_info: str) -> Tuple[str, dict]:
        """Parse language and attributes from code fence line"""
        # Match pattern like: python {filename="app.py" executable=true}
        match = re.match(r'^(\w+)\s*\{([^}]+)\}', lang_info)
        if match:
            lang = match.group(1)
            attrs_str = match.group(2)
            attributes = {}

            # Parse key=value or key="value" pairs
            for attr_match in re.finditer(r'(\w+)=(?:"([^"]*)"|(\S+))', attrs_str):
                key = attr_match.group(1)
                value = attr_match.group(2) or attr_match.group(3)
                attributes[key] = value

            return lang, attributes

        return lang_info, {}

    def _detect_filename(self, block: CodeBlock) -> Optional[str]:
        """Detect filename from first lines of code block or preceding heading"""
        # Priority 1: Explicit filename attribute in code fence
        if 'filename' in block.attributes:
            return block.attributes['filename']

        # Priority 2: Check first few lines for filename comments
        for line in block.content[:5]:
            for pattern in FILENAME_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    return match.group(1)

        # Priority 3: Use preceding heading if it looks like a filename
        if block.preceding_heading:
            heading = block.preceding_heading.strip()

            # Check if heading looks like a filename (has extension or common file patterns)
            # Match filenames with extensions
            if re.match(r'^([\w\-\.\/]+)[\w\-\.]+\.[a-zA-Z0-9]+', heading):
                return heading

        return None

    def _generate_filename(self, block: CodeBlock, base_name: str) -> str:
        """Generate filename for a code block"""
        detected = self._detect_filename(block)

        if detected and not self.args.numbered:
            # Validate file extension matches language
            _, ext = os.path.splitext(detected)
            name_ext = LANG_EXT.get(ext.lstrip("."), 'txt')
            lang_ext = LANG_EXT.get(block.language, 'txt')
            if name_ext == lang_ext or block.language == 'dockerfile' or block.language == 'makefile':
                return detected

        # Generate numbered filename
        lang_ext = LANG_EXT.get(block.language, 'txt')
        prefix = self.args.prefix or 'code'
        return f"{base_name}.{prefix}.{block.number}.{lang_ext}"

    def _should_process_block(self, block: CodeBlock) -> bool:
        """Check if block should be processed based on filters"""
        # Language filter
        if self.args.lang and block.language not in self.args.lang:
            return False

        # Block number filter
        if self.args.blocks and block.number not in self.args.blocks:
            return False

        # Exclude blocks
        if self.args.exclude_blocks and block.number in self.args.exclude_blocks:
            return False

        return True

    def _get_output_path(self, filename: str, root: str) -> str:
        """Determine output path for a file"""
        if self.args.flat:
            # Flatten all files to root directory
            return os.path.join(root, os.path.basename(filename))

        return os.path.join(root, filename)

    def _add_header(self, block: CodeBlock) -> List[str]:
        """Add header to code block if requested"""
        if not self.args.add_header:
            return block.content

        template = self.args.header_template or "Auto-generated from {source}"
        header = template.format(
            source=block.source_file,
            number=block.number,
            language=block.language,
            date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        comment_token = LANG_COMMENT.get(block.language, '#')
        if comment_token == '<!-- -->':
            header_line = f"<!-- {header} -->"
        elif comment_token == '/* */':
            header_line = f"/* {header} */"
        else:
            header_line = f"{comment_token} {header}"

        return [header_line, ''] + block.content

    def _file_exists_check(self, filepath: str) -> bool:
        """Check if file exists and handle according to options"""
        if not os.path.exists(filepath):
            return False

        if self.args.no_clobber:
            return True  # Skip overwriting

        if self.args.backup:
            backup_path = f"{filepath}.bak"
            shutil.copy2(filepath, backup_path)

        return False  # Proceed with overwriting

    def _write_block(self, block: CodeBlock, filepath: str) -> bool:
        """Write a code block to file"""
        try:
            # Create directory if needed
            dir_path = os.path.dirname(filepath)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            # Check if file exists
            if self._file_exists_check(filepath):
                if self.args.verbose:
                    print(
                        f"  Skipping existing file: {filepath}", file=sys.stderr)
                self.stats['files_skipped'] += 1
                return False

            # Get content with optional header
            content = self._add_header(block)

            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
                if content:  # Add final newline if there's content
                    f.write('\n')

            self.stats['files_created'] += 1
            return True

        except Exception as e:
            error_msg = f"Error writing {filepath}: {str(e)}"
            self.stats['errors'].append(error_msg)
            if not self.args.continue_on_error:
                raise
            return False

    def _show_diff(self, block: CodeBlock, existing_file: str):
        """Show diff between existing file and new content"""
        try:
            with open(existing_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()

            new_content = '\n'.join(block.content) + '\n'

            if existing_content != new_content:
                print(f"\n  DIFF for block #{block.number} ({existing_file}):")
                print(f"  File hash changed")
                # Could use difflib here for detailed diff
        except:
            raise

    def _interactive_prompt(self, block: CodeBlock, filepath: str) -> str:
        """Interactive prompt for each block"""
        print(f"\n  Block #{block.number} ({block.language})", file=sys.stderr)
        print(f"  Lines: {len(block.content)}", file=sys.stderr)
        print(f"  Output: {filepath}", file=sys.stderr)

        while True:
            response = input("  Save? [Y/n/s(kip all)] ").strip().lower()
            if response in ('', 'y', 'yes'):
                return 'save'
            elif response in ('n', 'no'):
                return 'skip'
            elif response in ('s', 'skip'):
                return 'skip_all'

    def save_metadata(self, root: str):
        """Save extraction metadata to JSON"""
        metadata = {
            'extraction_date': datetime.now().isoformat(),
            'source_files': list(set(b.source_file for b in self.blocks)),
            'total_blocks': len(self.blocks),
            'blocks': [b.to_dict() for b in self.blocks],
            'stats': self.stats,
        }

        manifest_path = os.path.join(root, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        if self.args.verbose:
            print(f"\n  Metadata saved to: {manifest_path}", file=sys.stderr)

    def print_stats(self):
        """Print extraction statistics"""
        print("\n" + "=" * 50, file=sys.stderr)
        print("EXTRACTION STATISTICS", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(
            f"Total blocks found: {self.stats['total_blocks']}", file=sys.stderr)
        print(f"Files created: {self.stats['files_created']}", file=sys.stderr)
        print(f"Files skipped: {self.stats['files_skipped']}", file=sys.stderr)

        if self.stats['languages']:
            print("\nLanguages:", file=sys.stderr)
            for lang, count in sorted(self.stats['languages'].items()):
                print(f"  {lang}: {count}", file=sys.stderr)

        if self.stats['errors']:
            print(f"\nErrors: {len(self.stats['errors'])}", file=sys.stderr)
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}", file=sys.stderr)

        print("=" * 50, file=sys.stderr)

    def process(self, input_files: List[str], root: str):
        """Main processing pipeline"""
        # Extract blocks from all files
        all_blocks = []
        for input_file in input_files:
            if self.args.verbose:
                print(f"\nProcessing: {input_file}", file=sys.stderr)

            blocks = self.extract_from_file(input_file)
            all_blocks.extend(blocks)

            # Update language stats
            for block in blocks:
                self.stats['languages'][block.language] = \
                    self.stats['languages'].get(block.language, 0) + 1

        self.blocks = all_blocks
        self.stats['total_blocks'] = len(all_blocks)

        if not all_blocks:
            print("No code blocks found!", file=sys.stderr)
            return

        # Dry run - just show what would be extracted
        if self.args.dry_run:
            print("\nDRY RUN - No files will be created", file=sys.stderr)
            for block in all_blocks:
                if self._should_process_block(block):
                    base_name = os.path.basename(block.source_file)
                    filename = self._generate_filename(block, base_name)
                    filepath = self._get_output_path(filename, root)
                    print(f"  Block #{block.number:3d} ({block.language:10s}) => {filepath}",
                          file=sys.stderr)
            return

        # Stats only mode
        if self.args.stats_only:
            self.print_stats()
            return

        # Create output directory
        if not self.args.dry_run and not os.path.exists(root):
            os.makedirs(root, exist_ok=True)
            if self.args.verbose:
                print(f"Created directory: {root}", file=sys.stderr)

        # Process blocks
        skip_all = False
        for block in all_blocks:
            if not self._should_process_block(block):
                continue

            base_name = os.path.basename(block.source_file)
            filename = self._generate_filename(block, base_name)
            block.filename = filename
            filepath = self._get_output_path(filename, root)

            # Interactive mode
            if self.args.interactive and not skip_all:
                action = self._interactive_prompt(block, filepath)
                if action == 'skip':
                    continue
                elif action == 'skip_all':
                    skip_all = True
                    continue

            # Diff mode
            if self.args.diff and os.path.exists(filepath):
                self._show_diff(block, filepath)
                continue

            # Write the file
            if self._write_block(block, filepath):
                if self.args.verbose or not self.args.quiet:
                    print(
                        f"  Block #{block.number:3d} => {filepath}", file=sys.stderr)

        # Save metadata
        if self.args.metadata:
            self.save_metadata(root)

        # Show statistics
        if self.args.stats or self.args.verbose:
            self.print_stats()
        else:
            print(
                f"\n  {self.stats['files_created']} code blocks extracted.", file=sys.stderr)


def find_markdown_files(path: str, recursive: bool = False) -> List[str]:
    """Find all markdown files in a path"""
    files = []

    if os.path.isfile(path):
        if path.endswith(('.md', '.markdown')):
            files.append(path)
    elif os.path.isdir(path):
        if recursive:
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    if filename.endswith(('.md', '.markdown')):
                        files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(path):
                filepath = os.path.join(path, filename)
                if os.path.isfile(filepath) and filename.endswith(('.md', '.markdown')):
                    files.append(filepath)

    return files


def load_config(config_file: str) -> dict:
    """Load configuration from YAML or JSON file"""
    if not os.path.exists(config_file):
        return {}

    try:
        import yaml
        with open(config_file, 'r') as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback to JSON if PyYAML not available
        with open(config_file, 'r') as f:
            return json.load(f)


def create_archive(root: str, format: str, output: str):
    """Create archive of extracted files"""
    if format == 'tar':
        import tarfile
        with tarfile.open(output, 'w:gz') as tar:
            tar.add(root, arcname=os.path.basename(root))
    elif format == 'zip':
        import zipfile
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root_dir, dirs, files in os.walk(root):
                for file in files:
                    filepath = os.path.join(root_dir, file)
                    arcname = os.path.relpath(filepath, root)
                    zipf.write(filepath, arcname)


def create_parser():
    parser = argparse.ArgumentParser(
        description='Extract code blocks from markdown files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s README.md
  %(prog)s -r output/ README.md
  %(prog)s --lang python,javascript --stats README.md
  %(prog)s --recursive docs/
  %(prog)s --dry-run --verbose README.md
        """
    )

    # Input/Output options
    parser.add_argument('files', nargs='*', help='Markdown files to process')
    parser.add_argument(
        '-r', '--root', help='Output directory (default: <file>.dir)')
    parser.add_argument('--recursive', action='store_true',
                        help='Recursively process directories')

    # Filtering options
    parser.add_argument(
        '--lang', help='Comma-separated list of languages to extract')
    parser.add_argument(
        '--blocks', help='Comma-separated list of block numbers to extract')
    parser.add_argument(
        '--exclude-blocks', help='Comma-separated list of block numbers to exclude')

    # Output formatting
    parser.add_argument('--flat', action='store_true',
                        help='Flatten output (ignore directory structure)')
    parser.add_argument('--numbered', action='store_true',
                        help='Always use numbered filenames')
    parser.add_argument(
        '--prefix', help='Custom filename prefix (default: code.)')

    # Behavior options
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be extracted without creating files')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Prompt for each code block')
    parser.add_argument('--no-clobber', action='store_true',
                        help='Do not overwrite existing files')
    parser.add_argument('--backup', action='store_true',
                        help='Create .bak files before overwriting')
    parser.add_argument('--continue-on-error', action='store_true',
                        help='Continue processing on errors')

    # Features
    parser.add_argument('--add-header', action='store_true',
                        help='Add header comment to extracted files')
    parser.add_argument('--header-template',
                        help='Custom header template (vars: {source}, {number}, {language}, {date})')
    parser.add_argument('--metadata', action='store_true',
                        help='Save extraction metadata to manifest.json')
    parser.add_argument('--diff', action='store_true',
                        help='Show diff for changed blocks')

    # Output control
    parser.add_argument('--stats', action='store_true',
                        help='Show extraction statistics')
    parser.add_argument('--stats-only', action='store_true',
                        help='Only show statistics, do not extract')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress output')

    # Archive options
    parser.add_argument('--archive', choices=['tar', 'zip'],
                        help='Create archive of extracted files')
    parser.add_argument('--archive-output', help='Archive output filename')

    # Config file
    parser.add_argument('--config', help='Load options from config file')
    return parser

def main():
    args = create_parser().parse_args()

    # Load config file if specified
    if args.config:
        config = load_config(args.config)
        # Merge config with command line args (command line takes precedence)
        for key, value in config.items():
            if not getattr(args, key, None):
                setattr(args, key, value)

    # Parse comma-separated lists
    if args.lang:
        args.lang = {lang.strip() for lang in args.lang.split(',')}
    if args.blocks:
        args.blocks = {int(b.strip()) for b in args.blocks.split(',')}
    if args.exclude_blocks:
        args.exclude_blocks = {int(b.strip())
                               for b in args.exclude_blocks.split(',')}

    # Determine input files
    if not args.files:
        # Check for default config file
        if os.path.exists('.extract-config.json'):
            config = load_config('.extract-config.json')
            args.files = config.get('files', [])

        if not args.files:
            parser.print_help()
            sys.exit(1)

    # Collect all markdown files
    input_files = []
    for path in args.files:
        input_files.extend(find_markdown_files(path, args.recursive))

    if not input_files:
        print("No markdown files found!", file=sys.stderr)
        sys.exit(1)

    # Determine output root
    if not args.root:
        if len(input_files) == 1:
            args.root = f"{input_files[0]}.dir"
        else:
            args.root = "extracted"

    # Process files
    extractor = CodeExtractor(args)
    extractor.process(input_files, args.root)

    # Create archive if requested
    if args.archive and not args.dry_run:
        archive_output = args.archive_output or f"extracted.{args.archive}"
        if args.verbose:
            print(f"\nCreating archive: {archive_output}", file=sys.stderr)
        create_archive(args.root, args.archive, archive_output)


if __name__ == '__main__':
    main()
