# Why native capture rather than a FireShot dependency?

FireShot provides a JavaScript capture API for webpages. It requires the extension
to be installed and its API option explicitly enabled; see the
[official API demo](https://t1.getfireshot.com/api.php) and
[activation requirements](https://getfireshot.com/api-required.php).
The provider lists Edge, Chrome, Brave and Firefox among supported browsers and
offers multi-page PDF and page-format features in Pro; see its
[feature overview](https://getfireshot.com/updated-lite.php).

For this product's fixed physical rectangles, ordered capture sets and guarded
Next navigation, a native Windows adapter gives one coordinate contract and
direct ownership of saved images, recovery and final PDF confirmation. Driving
extension menus and export dialogs would introduce more UI state. This is the
design rationale, not a claim that FireShot cannot be automated.

RectoFlow therefore does not require or integrate FireShot. It captures only the
visible configured screen regions and uses its own PDF export. A future adapter
could use FireShot's API, but it would need separate integration and licensing
verification; no such adapter is tested or shipped in this release.
