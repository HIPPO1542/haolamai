"""Check real imports in the selected interpreter; never claim readiness from metadata."""
import argparse
from datetime import datetime,timezone
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='outputs/environment_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+'.json')
    args=parser.parse_args()
    return subprocess.run([sys.executable,'-m','scripts.diagnose_environment','--output',args.output]).returncode


if __name__=='__main__':raise SystemExit(main())
