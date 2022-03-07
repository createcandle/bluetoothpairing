#!/bin/bash -e

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package SHA256SUMS

mkdir -p lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary :all: --prefix ""


# Prep new package
mkdir -p package

# Put package together
cp -r pkg lib LICENSE manifest.json *.py bluetooth_manufacturers.csv silence.wav README.md css images js views package/
find package -type f -name '*.pyc' -delete
find package -type f -name '._*' -delete
find package -type d -empty -delete
rm -rf package/pkg/pycache




# Generate checksums
echo "generating checksums"
cd package
find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
cd -

# Make the tarball
echo "creating archive"
TARFILE="bluetoothpairing-${version}.tgz"
tar czf ${TARFILE} package

shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum

rm -rf SHA256SUMS package
