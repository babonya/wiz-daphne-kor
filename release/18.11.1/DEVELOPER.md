# AI Developer Context & Spec Sheet (DEVELOPER.md)
This document is designed for AI coding assistants (like Gemini, Antigravity, etc.) to immediately understand the architecture, state transition system, and image coordinate specifications of the **Wizardry Daphne Dungeon Macro** for personal code modifications and debugging.

---

## 1. Project Directory & Component Roles
*   `main.py`: Acts as the central command tower. Manages global user configuration, ADB connection establishment, socket recovery guards (restarting Py process on socket death), and town-inn-village loop runs.
*   `dungeon_bot.py`: The core dungeon-runner state machine. Handles combat state, map navigation via image matching, poison/danger pixel scanning, and stuck recovery logic.
*   `chest_opener.py`: Manages trap-chest opening sequences, Yeolda UI detection, Milana (or designated disarmer) dynamic selection, and fast-click release minigame loop.
*   `party_manager.py`: Orchestrates healer-slot recognition, healer panel entry, automatic party heal approval, and field return validation.
*   `inn_manager.py`: Controls level-up approvals and temple resurrection sequences in the village-inn area.

---

## 2. Core State Machine (dungeon_bot.py)
The bot drives the macro using the following states:
*   `FIELD_WAIT`: Idle state on the dungeon field. Scans for chest buttons, exit buttons, poison triggers, or low-HP danger.
*   `AUTO_MOVING`: Triggered after tapping 'Move to Chest'. Scans for Yeolda popup or 'No Chest' toast messages.
*   `TRIGGER_EXIT`: Initiated when the chest toast message is captured. Continously taps the exit button to advance to the dungeon portal.
*   `IN_COMBAT`: Handles speed-up toggle (1x -> 2x) and executes character skills in designated turns (Yuzunamiki, Milana, etc.) before handing off to default auto-combat.
*   `BRANCH_CHECK`: Dispatched after tapping 'Open Chest'. Identifies whether a trap minigame or direct item loot screen is loaded.
*   `PLAY_MINIGAME`: Runs the high-speed spam clicking sequence to disarm chests.
*   `CLEAR_CHECK`: Clears the item loot toast window and summons the healer if low HP is detected.

---

## 3. Image Coordinate & Crop Specs (1440 * 2560 Emulator Specification)
To prevent template matching overlaps within the top-right 2x2 grid layout, coordinates must be crop-restricted:
*   **Button 1 (Speed/Speed-up)**: X=1216, Y=468
*   **Button 2 (Dungeon Exit/Escape)**: X=1335, Y=469
    *   *Exit scanner Crop*: `find_exit_button_coords` ➔ **X: 1250~1440, Y: 410~520**
*   **Button 3 (Checkpoint Auto-run)**: X=1215, Y=572
    *   *Checkpoint scanner Crop*: `find_checkpoint_button_coords` ➔ **X: 1150~1280, Y: 530~630**
*   **Button 4 (Auto-move to Chest)**: X=1327, Y=581
    *   *Chest scanner Crop*: `find_chest_button_coords` ➔ **X: 1250~1440, Y: 530~630**

---

## 4. Priority Sorting Mechanism
*   Both `party_manager.py` (for healers) and `chest_opener.py` (for disarmers) load templates using `sorted(glob.glob("templates/healer_*.png"))`.
*   This alphabetical/numerical sorting allows users to dictate priorities by editing file prefixes:
    *   `healer_1_ekaterina.png` is matched first.
    *   `healer_2_alice.png` is matched if Ekaterina is absent/dead.

---

## 5. Critical Fail-safes & Guard Blocks
1.  **'Yeolda' 소멸 검증 가드 (chest_opener.py)**:
    Before scanning for `disarmer_*.png` cards, the macro verifies if `yeolda_clean.png` has disappeared from the screen. Tapping is blocked if the chest standby menu is still visible to avoid false positive matches on the background rock texture.
2.  **'Yeolda' 터치 씹힘 재시도 (chest_opener.py)**:
    If `yeolda_clean.png` is continuously detected for more than 1.5 seconds, the macro forces a re-click on the 'Open' button coordinate `(width * 0.5, height * 0.795)`.
3.  **상자 갇힘 강제 탈출 (dungeon_bot.py)**:
    When stuck in `BRANCH_CHECK` for over 30 seconds with `yeolda_clean.png` still visible, the bot taps the 'Do Nothing' (아무것도 안 한다) coordinate `(width * 0.5, height * 0.855)` to close the popup and reset to `FIELD_WAIT`.
4.  **6인 독 감지 HSV 필터 (dungeon_bot.py)**:
    Scans slot coordinates in HSV range (H: 130~160, S: 40~255, V: 40~255) for purple pixels. If the purple area ratio exceeds 15% of a slot, it triggers the healer sequence.
