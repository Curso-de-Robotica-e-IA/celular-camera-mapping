import cv2


def click_on_image(image_path):
    clicked_points = []

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"Left click at ({x}, {y})")
            clicked_points.append((x, y))

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image '{image_path}' not found")

    cv2.namedWindow("Click Points")
    cv2.setMouseCallback("Click Points", mouse_callback)

    cv2.imshow("Click Points", img)
    while True:
        if cv2.waitKey(20) & 0xFF == 27:  # Optional: Press 'Esc' to quit
            break

    cv2.destroyAllWindows()
    return clicked_points
