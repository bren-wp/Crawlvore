"""Offline non-destructive recovery utility; use a new, nonexistent directory."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from data_safety import restore_workspace

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup',type=Path)
    parser.add_argument('new_workspace',type=Path)
    args=parser.parse_args()
    try:
        result=restore_workspace(args.backup,args.new_workspace)
    except (OSError,ValueError,RuntimeError) as error:
        parser.exit(1,'Recovery failed; original backup and existing workspaces were not overwritten. '+type(error).__name__+'\n')
    print('Verified recovered workspace:',result.parent)
