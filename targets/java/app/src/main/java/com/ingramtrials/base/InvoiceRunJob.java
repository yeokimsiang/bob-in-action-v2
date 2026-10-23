package com.ingramtrials.base;

public class InvoiceRunJob implements Job {
    public int execute(Desk desk) {
        return desk.invoiceBatch();
    }
}
