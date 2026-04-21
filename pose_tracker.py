import threading
import time
import cv2
import mediapipe as mp
import pygame as pg
from typing import Optional, Tuple

mp_pose = mp.solutions.pose

class HandPosition:
    def __init__(self, x: float, y: float, confidence: float = 1.0):
        self.x = x
        self.y = y
        self.confidence = confidence

class PoseTracker:
    def __init__(self, screen_w: int, screen_h: int, camera_index: int = 0):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.fallback = False
        self.current_frame = None
        self._left_hand = None
        self._right_hand = None
        self._lock = threading.Lock()
        self._running = True
        self._try_start_camera(camera_index)

    def _try_start_camera(self, camera_index):
        try:
            self._pose = mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0, # عشان جهازك Core i7 يفضل سريع
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self._thread = threading.Thread(target=self._camera_loop, args=(camera_index,), daemon=True)
            self._thread.start()
        except Exception as e:
            print(f"Error: {e}")
            self.fallback = True

    def _camera_loop(self, index):
        cap = cv2.VideoCapture(index)
        while self._running:
            ret, frame = cap.read()
            if not ret: continue

            # 1. تعديل الصورة (Flip & Rotate) عشان تظهر صح في Pygame
            frame = cv2.flip(frame, 1) # Mirror effect
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._pose.process(frame_rgb)

            # 2. تجهيز الصورة للعرض كخلفية
            # بنعمل Transpose عشان Pygame بيفهم الـ Width والـ Height بالعكس
            display_frame = cv2.transpose(frame_rgb)
            
            with self._lock:
                self.current_frame = display_frame
                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark
                    # تتبع الرسغ (Wrist) اليمين والشمال
                    self._left_hand = HandPosition(lm[15].x, lm[15].y, lm[15].visibility)
                    self._right_hand = HandPosition(lm[16].x, lm[16].y, lm[16].visibility)
            time.sleep(0.01)
        cap.release()

    def get_pixel_positions(self):
        """بترجع مكان الإيد الأكثر وضوحاً فقط لمنع ظهور دايرتين"""
        with self._lock:
            # بنقارن بين الإيد اليمين والشمال ونختار اللي الـ Confidence بتاعها أعلى
            best_hand = None
            max_conf = 0
            
            for h in [self._left_hand, self._right_hand]:
                if h and h.confidence > max_conf:
                    max_conf = h.confidence
                    best_hand = h
            
            # لو لقينا إيد واضحة بنسبة كافية (أكتر من 0.4) بنرجع مكانها بس
            if best_hand and best_hand.confidence > 0.4:
                px = int(best_hand.x * self.screen_w)
                py = int(best_hand.y * self.screen_h)
                return [(px, py)] # بنرجع قائمة فيها نقطة واحدة بس
            
            return [] # لو مفيش إيد واضحة بنرجع قائمة فاضية

    def draw_overlay(self, surf):
        """Draw hand indicators ONLY."""
        import pygame as pg 
        
        # رسم نقاط تتبع اليدين (الدوائر الفيروزية) لضمان التحكم الحركي
        positions = self.get_pixel_positions()
        for px, py in positions:
            # دايرة واحدة صلبة بلون الفيروز المعتمد في المشروع
            pg.draw.circle(surf, (64, 224, 208), (px, py), 22) 
            # إضافة إطار أبيض خفيف جداً عشان تبان فوق أي خلفية
            pg.draw.circle(surf, (255, 255, 255), (px, py), 22, 2)

    def stop(self):
        self._running = False