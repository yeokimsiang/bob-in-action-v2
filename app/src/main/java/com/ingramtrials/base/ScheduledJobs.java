package com.ingramtrials.base;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ScheduledJobs {
    final Desk desk;
    @Value("${demo.schedule.enabled:false}") boolean enabled;
    ScheduledJobs(Desk desk) { this.desk=desk; }
    @Scheduled(cron="${demo.schedule.invoice-cron:0 0 1 * * *}")
    public void invoiceRun() throws Exception { if (enabled) desk.runJob("invoices"); }
    @Scheduled(cron="${demo.schedule.credit-cron:0 30 1 * * *}")
    public void creditRun() throws Exception { if (enabled) desk.runJob("credit-notes"); }
}
