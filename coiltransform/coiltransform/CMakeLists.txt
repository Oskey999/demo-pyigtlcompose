cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(coiltransform)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/coiltransform")
set(EXTENSION_CONTRIBUTORS "Oscar Rafq (University of Western Australia)")
set(EXTENSION_DESCRIPTION "Attempt 1 at mesh oriented coil positioning")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/coiltransform.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/coiltransform/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(adjustpos)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
