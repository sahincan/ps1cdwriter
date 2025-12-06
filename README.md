# PS1 CD Writer
This application is a simple PyQt6-based frontend for cdrdao that allows you to burn PlayStation 1 .cue image files to a physical CD. After launching the program, first click Auto-detect Drive or manually enter your CD device path (e.g., /dev/sr0) and press Test Drive to verify that the disc is detected correctly. 

Next, choose your .cue file with Select CUE File, insert a writable CD, and press Burn. The log window will display all progress and messages from cdrdao, including success or error details. 

Make sure that your .cue and .bin files remain in the same folder.
