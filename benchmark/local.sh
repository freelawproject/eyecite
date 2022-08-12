#! /bin/bash

# Get current benchmark to test against the main branch
[ -d "eyecite/" ] && rm -rf eyecite/
cd "$PWD/../" && git clone "file:///$PWD" "$PWD/benchmark/eyecite/"
cd benchmark

curl $0 --output bulk-file.csv.bz2
cp benchmark.py eyecite/

cd eyecite/
poetry install --no-dev
poetry run python benchmark.py --branch current
cd ..
rm -rf eyecite/

git clone -b main https://github.com/freelawproject/eyecite.git eyecite
cp benchmark.py eyecite/
cd eyecite/
poetry install --no-dev
poetry run python benchmark.py --branch main
cd ..
rm -rf eyecite/
