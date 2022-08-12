#! /bin/bash

while getopts l:b:m:s: flag
do
    case "${flag}" in
        m) branch1=${OPTARG};;
        b) branch2=${OPTARG};;
        l) local=${OPTARG};;
        s) size=${OPTARG};;
    esac
done

# If size is flagged with a value grab the larger file to test with
if [ "$size" -eq  "1" ]
 then
   url=https://storage.courtlistener.com/bulk-data/eyecite/tests/ten-percent.csv.bz2
else
   url=https://storage.courtlistener.com/bulk-data/eyecite/tests/one-percent.csv.bz2
fi

[ -d "eyecite/" ] && rm -rf eyecite/
curl $url --output bulk-file.csv.bz2

# if local is flagged with a value - pass the url to local and run it using
# the current checked out local branch
if [ "$local" ]
 then

    [ -d "eyecite/" ] && rm -rf eyecite/
    cd "$PWD/../" && git clone "file:///$PWD" "$PWD/benchmark/eyecite/"
    cd benchmark

    curl $url --output bulk-file.csv.bz2
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

    branch1=current
    branch2=main

 else

    #Otherwise run this comparing two branches online.
    echo "Cloning $branch1 branch"
    git clone -b $branch1 https://github.com/freelawproject/eyecite.git
    cp benchmark.py eyecite/
    cd eyecite/
    poetry install --no-dev
    poetry run python benchmark.py --branch $branch1
    cd ..
    rm -rf eyecite/

    echo "Cloning $branch2 branch"
    git clone -b $branch2 https://github.com/freelawproject/eyecite.git
    cp benchmark.py eyecite/
    cd eyecite/
    poetry install --no-dev
    poetry run python benchmark.py --branch branch2
    cd ..
    rm -rf eyecite/

fi

# Generate new poetry installation and generate our charts and reports
poetry init --no-interaction
poetry add matplotlib pandas tables tabulate
poetry install --no-dev
poetry run python chart.py --branch1 $branch1 --branch2 $branch2

# Clean up and remove miscellaneous material
rm poetry.lock
rm pyproject.toml
rm bulk-file.csv.bz2

