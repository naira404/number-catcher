"""
Kawkabi - Number Catcher
Therapeutic math game for children with ADHD
Entry point
"""

import pygame
import sys
from game import NumberCatcherGame
import mediapipe as mp
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption("🌟 Kawkabi - Number Catcher")
    
    game = NumberCatcherGame(screen)
    game.run()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
