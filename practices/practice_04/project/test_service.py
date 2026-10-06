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


class ListSubscribersTest(unittest.TestCase):
    def setUp(self):
        subscribers.clear()

    def test_empty(self):
        self.assertEqual(service.list_subscribers(), [])

    def test_sorted(self):
        for name in ("Боб", "ann", "bob", "Ann", "Alice"):
            subscribe(name)
        self.assertEqual(service.list_subscribers(), ["Alice", "Ann", "ann", "bob", "Боб"])

    def test_duplicate(self):
        subscribe("Ann")
        subscribe(" Ann ")
        self.assertEqual(service.list_subscribers(), ["Ann"])

    def test_independent_list(self):
        subscribe("Ann")
        subscribe("Bob")
        names = service.list_subscribers()
        another_names = service.list_subscribers()
        self.assertIsNot(names, another_names)
        names.clear()
        names.append("Kate")
        self.assertEqual(subscribers, {"Ann", "Bob"})
        self.assertEqual(another_names, ["Ann", "Bob"])
        self.assertEqual(service.list_subscribers(), ["Ann", "Bob"])

    def test_subscribe_and_unsubscribe(self):
        subscribe(" Bob ")
        self.assertEqual(service.list_subscribers(), ["Bob"])
        subscribe("Ann")
        self.assertEqual(service.list_subscribers(), ["Ann", "Bob"])
        self.assertEqual(service.unsubscribe(" Bob "), {"unsubscribed": True})
        self.assertEqual(service.list_subscribers(), ["Ann"])
        self.assertEqual(service.unsubscribe("Bob"), {"unsubscribed": False})
        self.assertEqual(service.list_subscribers(), ["Ann"])
        self.assertEqual(service.unsubscribe("Ann"), {"unsubscribed": True})
        self.assertEqual(service.list_subscribers(), [])


if __name__ == "__main__":
    unittest.main()
