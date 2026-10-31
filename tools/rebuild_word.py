"""Optional Word reconstruction; does not overwrite the archived document."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    for name in ('build_document.py','edit_remove_origin_means.py'):
        subprocess.run([sys.executable,str(ROOT/'report/source'/name)],check=True)
    print('Reconstructed Word: '+str(ROOT/'reproduced/report/CEO_full_orbital_policy_2026-10-31_revised.docx'))
