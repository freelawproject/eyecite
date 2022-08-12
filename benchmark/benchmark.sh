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

curl $url --output bulk-file.csv.bz2

# if local is flagged with a value - pass the url to local and run it using
# the current checked out local branch
if [ "$local" ]
 then
   sh local.sh $url
   branch1=current
   branch2=main
 else

    #Otherwise run this comparing two branches online.
    [ -d "eyecite/" ] && rm -rf eyecite/

    curl $url --output bulk-file.csv.bz2
    ourBranches=($branch1 $branch2)

    for var in ${ourBranches[@]};
    do
        echo "Closing $var branch"
        git clone -b $var https://github.com/freelawproject/eyecite.git
        cp benchmark.py eyecite/
        cd eyecite
        poetry install --no-dev
        poetry run python benchmark.py --branch $var
        cd ..
        rm -rf eyecite/
    done

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

