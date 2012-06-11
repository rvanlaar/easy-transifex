#!/bin/bash

repo="http://code.indifex.com/transifex/"

if ! which rpmbuild &> /dev/null ; then
	echo "rpmbuild is not installed in your system; exiting"
	exit 1
fi

if [ ! "$#" = "1" ]; then
	echo "This script requires a single argument specifying the package version to build"
	echo "i.e. ./build.sh 1.2.3 for building version 1.2.3"
	exit 1
fi

function build {
rpmbuild --define "_builddir $1/BUILD" \
	--define "_buildrootdir $1/BUILDROOT" \
	--define "_rpmdir $1/RPMS" \
	--define "_sourcedir $1/SOURCES" \
	--define "_srcrpmdir $1/SRPMS" \
	--define "_build_name_fmt %%{name}-%%{version}-%%{release}.%%{arch}.rpm" \
	"$2" --nodeps "$1"/SPECS/transifex.spec
}

rootdir="$(mktemp -d -p $PWD -t txbuild-XXXXXXXX)"

for dir in BUILD BUILDROOT RPMS SOURCES SPECS SRPMS; do
	if [ ! -d "$rootdir/$dir" ]; then
		mkdir -p "$rootdir/$dir"
	fi
done

cp -p django-settings.py.in "$rootdir"/SOURCES

echo "applying version $1 to spec file"
sed -e "s/\[\[version\]\]/$1/g" SPECS/transifex.spec.in > "$rootdir"/SPECS/transifex.spec
echo "checking out latest code; please wait"
hg clone $repo "$rootdir"/SOURCES/transifex-$1

pushd "$rootdir"/SOURCES
echo "bundling ..."
tar cfz transifex-$1.tar.gz transifex-$1
rm -rf transifex-$1
popd

build "$rootdir" -bb || exit 1
build "$rootdir" -bs || exit 2

find "$rootdir" -name '*.rpm' -exec cp {} . \;
rm -rf "$rootdir"
