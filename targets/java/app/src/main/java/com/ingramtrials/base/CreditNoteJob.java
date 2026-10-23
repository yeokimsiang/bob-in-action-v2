package com.ingramtrials.base;

public class CreditNoteJob implements Job {
    public int execute(Desk desk) {
        return desk.creditBatch();
    }
}
