package com.ingramtrials.base;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class DeskMoneyTest {
    @Test
    void moneyUsesTwoPlaces() {
        assertEquals("1.01", Desk.money(new BigDecimal("1.005")));
    }
}
