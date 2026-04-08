#!/bin/bash -e

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

# Clean up from previous releases
echo "removing old files"
rm -rf *.tgz *.sha256sum package SHA256SUMS lib

ADDON_ARCH="$1"
#LANGUAGE_NAME="$2"
#PYTHON_VERSION="$3"
echo "ADDON_ARCH: $ADDON_ARCH"
echo
lscpu
echo ""
pwd
echo ""
echo "PYTHON_VERSION from env: $PYTHON_VERSION"

#if [ -z ${var+x} ]; then echo "var is unset"; else echo "var is set to '$var'"; fi

if [ -d /usr/bin/ ]; then
  echo "python versions available:"
  ls /usr/bin/python*
else
  echo "yikes, no /usr/bin ?"
fi

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

export PYTHONIOENCODING=utf8
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH="$HOME/.local/lib:/usr/local/lib:$LD_LIBRARY_PATH" LIBRARY_PATH="$HOME/.local/lib/" CFLAGS="-I$HOME/.local/include"

# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

if [ -z "${PYTHON_VERSION}" ]; then
    echo "YIKES, did NOT get Python version as a parameter."
    # assume the current python3 version is the target one
    PYTHON_VERSION="$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d. -f 1-2)"
    echo "PYTHON_VERSION from python3: $PYTHON_VERSION"
else
    # python version was explicitly provided
    echo "got Python version as a parameter: ${PYTHON_VERSION}"
fi
  

if [ -z "${ADDON_ARCH}" ]; then
  TARFILE_SUFFIX=
else
  TARFILE_SUFFIX="-${ADDON_ARCH}-v${PYTHON_VERSION}"
fi

echo "-----"
echo "TARFILE_SUFFIX: $TARFILE_SUFFIX"
echo "-----"

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
TARFILE="bluetoothpairing-${version}${TARFILE_SUFFIX}.tgz"
echo "TARFILE: $TARFILE"
tar czf ${TARFILE} package

shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum

rm -rf SHA256SUMS package
