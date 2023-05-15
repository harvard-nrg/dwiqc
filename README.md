# DWI QC Plugin #

Provides the DWIQC datatype and report page.

# Building #

To build the plugin:

1. Build the plugin: `./gradlew -Dhttp.proxyHost=rcproxy.rc.fas.harvard.edu -Dhttp.proxyPort=3128 -Dhttps.proxyHost=rcproxy.rc.fas.harvard.edu -Dhttps.proxyPort=3128 jar` This should build the plugin in the file **build/libs/dwiqc-plugin-1.0.0.jar** 

# Installation #

1. Copy the plugin jar to your plugins folder: `cp build/libs/dwiqc-plugin-1.0.0.jar /data/xnat/home/plugins`

