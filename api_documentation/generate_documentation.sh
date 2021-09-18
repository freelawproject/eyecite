#!/bin/bash
(pip3 install pdoc3);
(pdoc --html $(pwd)/../eyecite --output-dir $(pwd) --force);
(sed -i '' 's/AhocorasickTokenizer(.*\]))/AhocorasickTokenizer()/' $(pwd)/eyecite/find.html)  # Removes insanely-long parameter definition
(sed -i '' 's/AhocorasickTokenizer(.*\]))/AhocorasickTokenizer()/' $(pwd)/eyecite/index.html)  # Removes insanely-long parameter definition
