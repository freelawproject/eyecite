# Benchmarking

## Quick Start

Benchmarking runs thru the `benchmark.sh` bash script.

Comparing two branches online run 

    cd /path/to/benchmark/directory/
    sh benchmark.sh -b test-branch-one -m test-branch-two

the github repositiory action will automatically run 

    sh benchmark.sh -m main -b the-branch-for-the-pr

if you wish to run this test against your local repository vs head/main

    sh benchmarck.sh -l true (or any value) 

Additionally if you want to run the larger corpus for any of these
tests you can run the flag `-s` (size)
    
    sh benchmarck.sh -l true -s true

this will use the bulk data ten-percent file 


## Reports

The following commands will download or checkout various branches and 
compare the results. Aftewards it will generate a report comparing speed
gains/losses in quality for you to review.  If the changes are too great
you can review the outputs directory for the full comparison of the 
two branches.