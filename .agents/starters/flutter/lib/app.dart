import 'package:app/features/counter/presentation/screens/counter_screen.dart';
import 'package:app/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: CounterScreen(),
    );
  }
}
