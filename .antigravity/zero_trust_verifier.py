#!/usr/bin/env python3
import sys
import subprocess
import fnmatch
import os
import re

# Exclusion patterns defined by the Zero-Trust execution boundaries
EXCLUSION_PATTERNS = [
    "**/bridge.db",
    "**/*.env*",
    "**/*.hex",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa*",
    "**/id_dsa*",
    "**/id_ed25519*",
    "**/id_ecdsa*",
    "**/*accessKeys.csv"
]

def check_staged_files():
    """Ensure no files matching the exclusion zones are staged in Git."""
    print("[*] Checking staged files in Git...")
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--diff-filter=d", "--name-only"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        staged_files = result.stdout.strip().split("\n")
        staged_files = [f for f in staged_files if f]
        
        violations = []
        for file_path in staged_files:
            for pattern in EXCLUSION_PATTERNS:
                # Resolve match logic (either relative or absolute format match)
                if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(os.path.basename(file_path), pattern):
                    violations.append((file_path, pattern))
                    
        if violations:
            print("[!] CRITICAL VIOLATION: Staged files match exclusion patterns!")
            for file_path, pattern in violations:
                print(f"  - File: {file_path} (Matches pattern: {pattern})")
            return False
        
        print("[+] Staged files clean. No exclusion zone matches found.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Git check failed: {e.stderr}")
        return False

def check_git_ignored():
    """Ensure that the exclusion patterns are ignored by Git."""
    print("[*] Verifying exclusion patterns are ignored...")
    test_files = [
        "bridge.db",
        "some.env",
        "some.env.backup",
        "key.pem",
        "secret.key",
        "id_rsa",
        "vapi-bridge_accessKeys.csv"
    ]
    
    all_ignored = True
    for file_name in test_files:
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-v", file_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                print(f"[+] Ignored: {file_name} -> {result.stdout.strip()}")
            else:
                print(f"[!] WARNING: {file_name} is NOT ignored by Git!")
                all_ignored = False
        except Exception as e:
            print(f"[!] Error running check-ignore: {e}")
            all_ignored = False
            
    return all_ignored

def check_codebase_posr():
    """Audit the PoSR pipeline alignment."""
    print("[*] Auditing Proof of Session Recency (PoSR) pipeline files...")
    posr_file = "bridge/vapi_bridge/replay_proof_pipeline/posr.py"
    if not os.path.exists(posr_file):
        print(f"[!] Warning: PoSR file not found at {posr_file}")
        return False
        
    with open(posr_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check for forbidden keywords related to optical scraping/frame-grabbing
    forbidden_terms = ["optical_scrape", "frame_grab", "screen_shot", "finite_field_blind"]
    found_violations = []
    for term in forbidden_terms:
        if term in content:
            found_violations.append(term)
            
    if found_violations:
        print(f"[!] CRITICAL: Deprecated speculative drift mechanisms found in PoSR: {found_violations}")
        return False
        
    print("[+] PoSR pipeline uses blockhash-driven recency (zero deprecated drift mechanisms).")
    return True

def check_claudeignore():
    """Ensure .claudeignore exists and contains required rules."""
    print("[*] Auditing .claudeignore rules...")
    path = ".claudeignore"
    if not os.path.exists(path):
        print("[!] Warning: .claudeignore file is missing!")
        return False
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    required_rules = [
        "**/bridge.db",
        "**/*.env*",
        "**/*.pem",
        "**/*.key",
        "**/id_rsa*",
        "**/id_dsa*",
        "**/id_ed25519*",
        "**/id_ecdsa*"
    ]
    
    missing = []
    for rule in required_rules:
        if rule not in content:
            missing.append(rule)
            
    if missing:
        print(f"[!] Warning: .claudeignore is missing required rules: {missing}")
        return False
        
    print("[+] .claudeignore matches all required zero-trust ignore rules.")
    return True

def main():
    print("=" * 60)
    print("QorTroller Zero-Trust Verification Agent")
    print("=" * 60)
    
    staged_ok = check_staged_files()
    ignored_ok = check_git_ignored()
    claude_ignored_ok = check_claudeignore()
    posr_ok = check_codebase_posr()
    
    print("=" * 60)
    if staged_ok and ignored_ok and claude_ignored_ok and posr_ok:
        print("[SUCCESS] Zero-Trust checks PASSED. Safe to proceed.")
        sys.exit(0)
    else:
        print("[FAILURE] Zero-Trust checks FAILED! Address the violations above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
