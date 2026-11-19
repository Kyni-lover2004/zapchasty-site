"""Проверки смены состояния мониторинга без отправки реальных сообщений."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class MonitorTests(SimpleTestCase):
    @override_settings(SHOP_ALERTS_ENABLED=False)
    def test_alerts_are_disabled_without_explicit_configuration(self):
        """Обычная проверка не обращается в Telegram."""
        from .management.commands.check_site import send_alert
        with patch('shop.management.commands.check_site.urlopen') as request:
            send_alert(False)
        request.assert_not_called()

    def test_failure_and_recovery_notify_only_on_transitions(self):
        """Повторный сбой не дублирует уведомление, восстановление отмечается один раз."""
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state.json'
            with patch('shop.management.commands.check_site.check_availability', side_effect=[True, False, False, True]), patch('shop.management.commands.check_site.send_alert') as alert:
                call_command('check_site', state_file=str(state))
                with self.assertRaises(CommandError):
                    call_command('check_site', state_file=str(state))
                with self.assertRaises(CommandError):
                    call_command('check_site', state_file=str(state))
                call_command('check_site', state_file=str(state))
            self.assertEqual([call.args[0] for call in alert.call_args_list], [False, True])
            self.assertTrue(json.loads(state.read_text())['available'])
