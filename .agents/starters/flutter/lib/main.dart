import 'package:app/app.dart';
import 'package:app/core/services/crash.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Crash.init(appRunner: () => runApp(const ProviderScope(child: App())));
}
