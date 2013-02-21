rm -rf thin
BINFOLDER=$1
LIST=`cd $BINFOLDER; ls Qt* *.so *.dylib Python 2>/dev/null`
for FILE in $LIST
do
	ISFAT=`lipo -info $BINFOLDER/$FILE|grep -v Non-fat`
	if [ "$ISFAT" != "" ]
	then
		echo "Fat Binary:  $FILE"
		mkdir -p thin
		lipo -thin i386 -output thin/$FILE $BINFOLDER/$FILE 
	fi
done

if [ -d thin ]
then 
	mv thin/* $BINFOLDER
else
	echo No files to lipo
fi
rm -rf thin
