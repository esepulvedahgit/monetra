import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/dashboard.dart';
import '../models/transaction.dart';
import '../providers/auth_provider.dart';
import '../services/dashboard_service.dart';
import '../services/transaction_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  DashboardSummary? _summary;
  List<Transaction> _transactions = [];
  bool _loading = true;
  String? _error;

  final now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final summary = await DashboardService.summary(
          year: now.year, month: now.month);
      final txResult = await TransactionService.list(
          year: now.year, month: now.month);
      setState(() {
        _summary = summary;
        _transactions = txResult.transactions;
      });
    } catch (e) {
      setState(() { _error = e.toString(); });
    } finally {
      setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    const green = Color(0xFF00C896);
    final user = context.read<AuthProvider>().user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Monetra',
            style: TextStyle(fontWeight: FontWeight.w900)),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Cerrar sesión',
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!,
                  style: const TextStyle(color: Color(0xFFEF4444))))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Text('Hola, ${user?.username ?? ''}',
                          style: const TextStyle(
                              fontSize: 22, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text('${now.year} — mes ${now.month}',
                          style: TextStyle(color: Colors.grey[400])),
                      const SizedBox(height: 20),
                      if (_summary != null) ...[
                        _SummaryCard(summary: _summary!),
                        const SizedBox(height: 20),
                      ],
                      const Text('Transacciones del mes',
                          style: TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 8),
                      ..._transactions.map((tx) => _TxTile(tx: tx)),
                    ],
                  ),
                ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final DashboardSummary summary;
  const _SummaryCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _Stat('Ingresos', summary.totalIncome, const Color(0xFF00C896)),
                _Stat('Gastos', summary.totalExpense, const Color(0xFFEF4444)),
                _Stat('Balance', summary.balance,
                    summary.balance >= 0
                        ? const Color(0xFF00C896)
                        : const Color(0xFFEF4444)),
              ],
            ),
            if (summary.budgetAmount > 0) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: (summary.budgetUsedPct ?? 0) / 100,
                backgroundColor: Colors.grey[800],
                color: (summary.budgetUsedPct ?? 0) > 90
                    ? const Color(0xFFEF4444)
                    : const Color(0xFF00C896),
              ),
              const SizedBox(height: 4),
              Text(
                  'Presupuesto: ${summary.budgetUsedPct?.toStringAsFixed(1) ?? 0}% usado',
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ],
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final double value;
  final Color color;
  const _Stat(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
        const SizedBox(height: 4),
        Text(value.toStringAsFixed(0),
            style: TextStyle(
                fontSize: 18, fontWeight: FontWeight.bold, color: color)),
      ],
    );
  }
}

class _TxTile extends StatelessWidget {
  final Transaction tx;
  const _TxTile({required this.tx});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: tx.isExpense
            ? const Color(0x33EF4444)
            : const Color(0x3300C896),
        child: Icon(
          tx.isExpense ? Icons.arrow_downward : Icons.arrow_upward,
          color: tx.isExpense
              ? const Color(0xFFEF4444)
              : const Color(0xFF00C896),
          size: 18,
        ),
      ),
      title: Text(tx.description ?? tx.categoryName ?? '—'),
      subtitle: Text('${tx.categoryName ?? ''} · ${tx.date}',
          style: const TextStyle(fontSize: 12)),
      trailing: Text(
        '${tx.isExpense ? '-' : '+'}${tx.amount.toStringAsFixed(0)}',
        style: TextStyle(
          fontWeight: FontWeight.bold,
          color: tx.isExpense
              ? const Color(0xFFEF4444)
              : const Color(0xFF00C896),
        ),
      ),
    );
  }
}
