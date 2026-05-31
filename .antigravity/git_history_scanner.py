#!/usr/bin/env python3
import subprocess
import sys
import re

def run_git_cmd(args):
    try:
        res = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"[!] Git command failed: git {' '.join(args)}")
        print(f"Error: {e.stderr}")
        return ""

def scan_historical_filenames():
    print("[*] Scanning all historical filenames ever committed in Git...")
    output = run_git_cmd(["log", "--all", "--full-history", "--name-only", "--format="])
    files = set(filter(None, [line.strip() for line in output.split("\n")]))
    
    sensitive_patterns = [
        r"\.env$",
        r"\.env\.",
        r"bridge\.db$",
        r"\.pem$",
        r"\.key$",
        r"id_rsa",
        r"id_dsa",
        r"id_ed25519",
        r"id_ecdsa",
        r"accessKeys\.csv$"
    ]
    
    leaks = []
    for file in files:
        for pattern in sensitive_patterns:
            if re.search(pattern, file, re.IGNORECASE):
                leaks.append(file)
                break
                
    if leaks:
        print("[!] Found historically committed files matching sensitive patterns:")
        for leak in sorted(leaks):
            print(f"  - {leak}")
        return leaks
    else:
        print("[+] No sensitive file patterns ever committed in Git history.")
        return []

def scan_historical_contents():
    print("[*] Scanning historical diffs for private key headers...")
    # Patterns to look for in patch diffs
    key_markers = [
        "BEGIN EC PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "BEGIN PRIVATE KEY",
        "BEGIN CERTIFICATE",
        "private_key",
        "aws_access_key_id",
        "aws_secret_access_key"
    ]
    
    found_commits = {}
    for marker in key_markers:
        stdout = run_git_cmd(["log", "-S", marker, "--oneline"])
        commits = [line.strip() for line in stdout.split("\n") if line.strip()]
        if commits:
            found_commits[marker] = commits
            
    if found_commits:
        print("[!] Found commits matching secret headers/keys:")
        for marker, commits in found_commits.items():
            print(f"  - Pattern '{marker}' found in commits:")
            for commit in commits:
                print(f"    * {commit}")
        return found_commits
    else:
        print("[+] No secret headers or keys found in Git history diffs.")
        return {}

def main():
    print("=" * 60)
    print("QorTroller Git History Secrets Scanner")
    print("=" * 60)
    
    leaked_files = scan_historical_filenames()
    leaked_contents = scan_historical_contents()
    
    print("=" * 60)
    if leaked_files or leaked_contents:
        print("[AUDIT WARNING] Potential historical secret leaks detected in Git history!")
        print("\nTo purge legacy exposures, run:")
        print("git-filter-repo --path <path_to_file> --invert-paths")
        print("or use BFG Repo-Cleaner: bfg --delete-files <filename>")
        sys.exit(1)
    else:
        print("[AUDIT SUCCESS] Git history is clean of secrets.")
        sys.exit(0)

if __name__ == "__main__":
    main()
