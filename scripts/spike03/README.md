# Qualification spike (not a product feature)

Commit this directory/contract/workflow first; execute on that clean subject.
Outputs must be in `.build-spike03/<unique-session>` in the canonical repository.
Never reuse a completed output folder. Do not remove old review evidence.

Native Windows x64 Python3.11/3.12, exact candidates in requirements.txt.
Use a separate venv; prepare.py downloads actual wheels, checks every SHA against
version-specific PyPI metadata, retains original licensing materials, installs
offline and runs pip check. No substitutions or global installation.

```
python scripts/spike03/prepare.py .build-spike03/<session>/prepared
python scripts/spike03/harness.py --output .build-spike03/<session>/source
python scripts/spike03/build.py .build-spike03/<session>/bundle .build-spike03/<session>/prepared
python scripts/spike03/harness.py --output .build-spike03/<session>/frozen --exe .build-spike03/<session>/bundle/relocated/RectoFlowSpike03/RectoFlowSpike03.exe
```

The last command executes actual relocated workers with clean PATH. An App-Control
denial means NOT_EXECUTED, not PASS; stop attempts on that host. Hosted proof is
reported separately. Full-memory RGB/noise cases measure1/12/24/48/64MP once each
and preserve PNG hashes/size. These are measured synthetic workloads, not a
universal performance guarantee or production limit validation.

CONTAINER_PAGE_1 is exercised by a spike policy probe using actual provider
frames. It is not evidence of a production adapter/detection implementation.
Proposal acceptance stays REVIEW_REQUIRED even for container-defined pages.

Source Python3.11 and Python3.12/frozen each report independently. Parent kill is
restricted to the own test parent, with a retained handle for its own worker PID.
Job Objects are not an exploit sandbox. Sources are generated locally; passwords
are ephemeral, pipe-only, never serialized in requests/logs/reports.

Unqualified batch/input/disk limits and missing failure-boundary proofs must be
listed as REQUIRED_CHANGE/open proof, not concealed by green primitive checks.
Run current129 product regressions separately. Archive durable summary/evidence
after execution in a distinct commit; retain tested subject SHA/tree.
