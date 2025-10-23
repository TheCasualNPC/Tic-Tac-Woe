# Tic Tac Woe
A tiny Python game. You can either run it directly with Python or build an EXE yourself


## 🧩 Requirements

- **Windows 10/11**
- **Python 3.10 or newer**

Make sure Python is added to your PATH during installation (tick “Add Python to PATH”).


## How to Run the Game

1. **Install Python**

   Download and install from [https://www.python.org/downloads/](https://www.python.org/downloads/).

2. **Open Command Prompt in the game’s folder**

         pip install pygame

3. **Run the game**

in the cmd directory you put the files run


    python "Tic Tac Woe.pyw"

as long as the .ogg and pyw are in the same folder the music will play with the game. 

4. **if you want to build the exe yourself**

         pip install pyinstaller
   
       pyinstaller --onefile --windowed --icon "Tic Tac Woe.ico" --add-data "game_theme.ogg;." --name TicTacWoe "Tic Tac Woe.pyw"

