import unittest

from toxic_backend.app.services.model_service import predict_message


class ModelServiceTests(unittest.TestCase):
    def test_representative_game_chat_predictions_use_six_class_labels(self):
        self.assertEqual(predict_message("good game everyone")["prediction"], "Non-Toxic")
        self.assertEqual(predict_message("you are a fool")["prediction"], "Insults & Flaming")
        self.assertEqual(predict_message("fuck you")["prediction"], "Insults & Flaming")

        explicit_threat = predict_message("i will kill you")
        self.assertEqual(explicit_threat["prediction"], "Threats")
        self.assertEqual(explicit_threat["status"], "Toxic")
        self.assertFalse(explicit_threat["confidence_is_calibrated"])
        self.assertEqual(
            explicit_threat["selected_model"],
            "Balanced Linear SVM, C=0.5 (uncalibrated score)",
        )

    def test_game_context_is_not_classified_as_a_threat_by_keyword(self):
        result = predict_message("i will kill it in the game")

        self.assertEqual(result["prediction"], "Non-Toxic")
        self.assertEqual(result["status"], "Safe")


if __name__ == "__main__":
    unittest.main()
