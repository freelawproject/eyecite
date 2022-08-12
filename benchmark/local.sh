#! /bin/bash

# Get current benchmark to test against the main branch

pwd
[ -d "eyecite/" ] && rm -rf eyecite/
cd "$PWD/../" && git clone "file:///$PWD" "$PWD/benchmark/eyecite/"
cd benchmark
pwd
curl https://storage.courtlistener.com/bulk-data/eyecite/tests/one-percent.csv.bz2 --output one-percent.csv.bz2
cp benchmark.py eyecite/

cd eyecite
poetry install --no-dev
poetry run python benchmark.py --branch current
cd ..
rm -rf eyecite/

PWD
git clone -b main https://github.com/freelawproject/eyecite.git eyecite
cp benchmark.py eyecite/
#cp one-percent.csv.bz2 eyecite/
cd eyecite
poetry install --no-dev
poetry run python benchmark.py --branch main
cd ..
rm -rf eyecite/

echo "Now lets compare our files and generate a graph we can use"

poetry init --no-interaction
poetry add matplotlib pandas tables tabulate
poetry install --no-dev
poetry run python chart.py --branch1 main --branch2 current
#
# Clean up and remove miscellaneous material
rm poetry.lock
rm pyproject.toml
rm one-percent.csv.bz2

