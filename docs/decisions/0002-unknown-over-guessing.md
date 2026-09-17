# ADR 0002: Unknown Over Guessing

When a parser cannot establish a value reliably, Radar returns no asserted
value or an explicit unknown classification. Precision is preferred over
invented coverage because false facts damage trust in the graph.
