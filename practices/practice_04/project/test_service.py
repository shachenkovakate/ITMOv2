import unittest
import service
from service import subscribe, subscribers


class SubscribeTest(unittest.TestCase):
    def setUp(self):
        subscribers.clear()

    def test_subscribe(self):
        self.assertEqual(subscribe("Ann"), {"subscribed": True})
        self.assertEqual(subscribers, {"Ann"})

    def test_empty(self):
        with self.assertRaises(ValueError):
            subscribe(" ")

    def test_duplicate(self):
        subscribe("Ann")
        subscribe("Ann")
        self.assertEqual(len(subscribers), 1)


class UnsubscribeTest(unittest.TestCase):
    def setUp(self):
        subscribers.clear()

    def test_unsubscribe(self):
        subscribe("Ann")
        self.assertEqual(service.unsubscribe("Ann"), {"unsubscribed": True})
        self.assertEqual(subscribers, set())

    def test_unknown(self):
        subscribe("Bob")
        self.assertEqual(service.unsubscribe("Ann"), {"unsubscribed": False})
        self.assertEqual(subscribers, {"Bob"})

    def test_repeat(self):
        subscribe("Ann")
        service.unsubscribe("Ann")
        self.assertEqual(service.unsubscribe("Ann"), {"unsubscribed": False})
        self.assertEqual(subscribers, set())

    def test_surrounding_spaces(self):
        subscribe(" Ann ")
        self.assertEqual(service.unsubscribe(" Ann "), {"unsubscribed": True})
        self.assertEqual(subscribers, set())

    def test_empty(self):
        subscribe("Bob")
        for name in ("", "   "):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "^empty name$"):
                    service.unsubscribe(name)
                self.assertEqual(subscribers, {"Bob"})

    def test_preserves_other_subscribers(self):
        for name in ("Ann", "Bob", "Kate"):
            subscribe(name)
        self.assertEqual(service.unsubscribe("Ann"), {"unsubscribed": True})
        self.assertEqual(subscribers, {"Bob", "Kate"})


if __name__ == "__main__":
    unittest.main()
