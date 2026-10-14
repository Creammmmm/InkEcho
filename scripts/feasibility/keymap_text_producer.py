"""Fixed-sample producer for the isolated guardian's requester-death test.

One outstanding character maximum. The next character cannot be produced until
its previous request is acknowledged. This is not a production transport.
"""

import json
import sys

for character in sys.argv[1]:
    print(json.dumps(character), flush=True)
    if sys.stdin.readline() != "ack\n":
        break
