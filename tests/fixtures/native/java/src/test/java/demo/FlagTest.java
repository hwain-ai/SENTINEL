package demo;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.Test;
final class FlagTest {
    @Test void enabledByDefault() { assertTrue(new Flag().enabled()); }
}
